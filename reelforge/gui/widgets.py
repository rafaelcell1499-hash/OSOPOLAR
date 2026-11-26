"""Widgets propios: tarjetas, rejillas de checks, sliders con valor, forma de onda con cortes y curva de velocidad."""
from __future__ import annotations
import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush, QPainterPath, QFont
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QWidget, QGridLayout, QCheckBox, QHBoxLayout,
                               QSlider, QSizePolicy)
from . import theme
from .. import speed as speedmod


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(16, 14, 16, 14)
        self.v.setSpacing(8)
        if title:
            t = QLabel(title.upper())
            t.setObjectName("cardTitle")
            self.v.addWidget(t)

    def add(self, w):
        self.v.addWidget(w)
        return w

    def addLayout(self, l):
        self.v.addLayout(l)


class CheckGrid(QWidget):
    changed = Signal()

    def __init__(self, items, cols=2, parent=None):
        super().__init__(parent)
        self.boxes: dict[str, QCheckBox] = {}
        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(16)
        for i, (key, label) in enumerate(items):
            cb = QCheckBox(label)
            cb.toggled.connect(lambda _=None: self.changed.emit())
            self.boxes[key] = cb
            g.addWidget(cb, i // cols, i % cols)

    def checked(self):
        return [k for k, b in self.boxes.items() if b.isChecked()]

    def set_checked(self, keys):
        for k, b in self.boxes.items():
            b.blockSignals(True)
            b.setChecked(k in keys)
            b.blockSignals(False)
        self.changed.emit()

    def set_all(self, on: bool):
        self.set_checked(list(self.boxes) if on else [])


class SliderRow(QWidget):
    changed = Signal(float)

    def __init__(self, label, lo, hi, val, step=0.01, fmt="{:.2f}", parent=None):
        super().__init__(parent)
        self.step, self.fmt = step, fmt
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.lab = QLabel(label)
        self.lab.setMinimumWidth(150)
        self.s = QSlider(Qt.Horizontal)
        self.s.setRange(int(round(lo / step)), int(round(hi / step)))
        self.val = QLabel()
        self.val.setMinimumWidth(48)
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.lab)
        h.addWidget(self.s, 1)
        h.addWidget(self.val)
        self.s.valueChanged.connect(self._ch)
        self.set_value(val)

    def _ch(self, _):
        self.val.setText(self.fmt.format(self.value()))
        self.changed.emit(self.value())

    def value(self) -> float:
        return self.s.value() * self.step

    def set_value(self, v: float):
        self.s.setValue(int(round(v / self.step)))
        self.val.setText(self.fmt.format(self.value()))


SPEED_COLORS = {"impact": "#ff6a1f", "rampup": "#ffb21f", "bullet": "#3ddc97", "pulse": "#6aa8ff",
                "none": "#4a4f63"}


class WaveformView(QWidget):
    """Forma de onda + energía + beats + ventana elegida + cortes planificados."""
    startChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.an = None
        self.win = (0.0, 0.0)
        self.plan = None
        self.setCursor(Qt.PointingHandCursor)

    def set_analysis(self, an):
        self.an = an
        self.update()

    def set_window(self, a, b):
        self.win = (a, b)
        self.update()

    def set_plan(self, plan):
        self.plan = plan
        self.update()

    def mousePressEvent(self, e):
        if self.an:
            t = e.position().x() / max(1, self.width()) * self.an.duration
            self.startChanged.emit(float(t))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setBrush(QColor(theme.PANEL))
        p.setPen(QPen(QColor(theme.BORDER)))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        if not self.an:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignCenter, "Carga un audio y pulsa «Analizar» para ver la forma de onda, los beats y los cortes")
            return
        an = self.an
        W, H = r.width(), r.height()
        mid = H * 0.5
        x_of = lambda t: t / an.duration * W
        # ventana
        a, b = self.win
        if b > a:
            p.fillRect(QRectF(x_of(a), 1, x_of(b) - x_of(a), H - 2), QColor(255, 106, 31, 38))
        # onda
        pk = an.peaks
        n = len(pk)
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, QColor(theme.ACCENT2))
        g.setColorAt(1, QColor(theme.ACCENT))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        bw = max(1.0, W / n)
        for i, v in enumerate(pk):
            hh = max(1.0, v * (H * 0.36))
            p.drawRect(QRectF(i * W / n, mid - hh, bw * 0.8, hh * 2))
        # energía
        path = QPainterPath()
        for i, e in enumerate(an.energy):
            x, y = x_of(an.energy_t[i]), H - 6 - e * (H * 0.32)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(61, 220, 151, 200), 1.6))
        p.drawPath(path)
        # beats
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for t in an.beats:
            x = x_of(t)
            p.drawLine(QPointF(x, 4), QPointF(x, H - 4))
        # cortes planificados
        if self.plan:
            for sg in self.plan.segs:
                x = x_of(sg.B0)
                col = QColor(SPEED_COLORS.get(sg.speed_kind, "#fff"))
                p.setPen(QPen(col, 2))
                p.drawLine(QPointF(x, 0), QPointF(x, 14))
                if sg.fire:
                    p.setPen(QPen(QColor("#ff3b1f"), 3))
                    p.drawPoint(QPointF(x, H - 4))
        # ventana bordes
        if b > a:
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.drawLine(QPointF(x_of(a), 0), QPointF(x_of(a), H))
            p.drawLine(QPointF(x_of(b), 0), QPointF(x_of(b), H))
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QPointF(8, 14), f"{an.tempo:.0f} BPM")


class CurveView(QWidget):
    """Dibuja el perfil de velocidad de los tipos de curva marcados."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.kinds, self.w = [], 0.6

    def set_data(self, kinds, w):
        self.kinds, self.w = kinds, w
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor(theme.PANEL2))
        p.setPen(QPen(QColor(theme.BORDER)))
        p.drawRoundedRect(r, 8, 8)
        W, H = r.width(), r.height()
        p.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine))
        p.drawLine(QPointF(8, H * 0.55), QPointF(W - 8, H * 0.55))   # velocidad 1x
        for k in self.kinds:
            if k == "none":
                continue
            prof = speedmod.profile(k, self.w, 1.0, 80)
            path = QPainterPath()
            for i, v in enumerate(prof):
                v = min(v, 3.2)
                x = 8 + i / (len(prof) - 1) * (W - 16)
                y = H - 8 - (v / 3.2) * (H - 16) * 0.95
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(SPEED_COLORS.get(k, "#fff")), 2.2))
            p.drawPath(path)
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QPointF(10, 14), "velocidad (arriba = rápido · abajo = cámara lenta)")
