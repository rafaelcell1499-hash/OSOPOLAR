"""Ventana principal de ReelForge."""
from __future__ import annotations
import os, json, random, time
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QStackedWidget, QPushButton, QFileDialog, QComboBox, QCheckBox, QSpinBox,
                               QDoubleSpinBox, QLineEdit, QPlainTextEdit, QProgressBar, QScrollArea, QSplitter,
                               QMessageBox, QColorDialog, QSizePolicy)
from .. import __version__, APP_NAME, audio, director, engine, ffutil
from ..config import (Settings, apply_preset, PRESETS, SYNC_MODES, SPEED_KINDS, CAMERA_FX, LOOKS, TRANSITIONS,
                      ACCENTS, TEXT_MODES, TEXT_STYLES, TEXT_POS, RESOLUTIONS)
from . import theme
from .widgets import Card, CheckGrid, SliderRow, WaveformView, CurveView
from .worker import AnalyzeWorker, RenderWorker

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}

try:
    if os.environ.get("REELFORGE_NO_PLAYER"):
        raise ImportError("reproductor desactivado")
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_PLAYER = True
except Exception:  # pragma: no cover
    HAS_PLAYER = False


def combo(items, parent=None):
    c = QComboBox(parent)
    for k, label in items:
        c.addItem(label, k)
    return c


def set_combo(c: QComboBox, key):
    i = c.findData(key)
    if i >= 0:
        c.setCurrentIndex(i)


def scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(widget)
    sa.setFrameShape(QScrollArea.NoFrame)
    return sa


def page(*cards) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 8, 0)
    v.setSpacing(12)
    for c in cards:
        v.addWidget(c)
    v.addStretch(1)
    return w


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__} — Reels Edit Studio")
        self.resize(1360, 880)
        self.setAcceptDrops(True)
        self.an = None
        self.worker = None
        self.analyzer = None
        self.audio_path = ""
        self.text_color = "#ffffff"
        self.text_font = ""
        self.last_out = ""
        self._t0 = 0.0

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # cabecera
        head = QHBoxLayout()
        logo = QLabel("🔥 ReelForge")
        logo.setObjectName("logo")
        sub = QLabel("Editor automático de reels · curvas de velocidad · beat-sync · fuego · looks · texto")
        sub.setObjectName("muted")
        head.addWidget(logo)
        head.addWidget(sub)
        head.addStretch(1)
        self.cmb_preset = combo([(k, k) for k in PRESETS])
        self.cmb_preset.setMinimumWidth(200)
        head.addWidget(QLabel("Estilo:"))
        head.addWidget(self.cmb_preset)
        outer.addLayout(head)

        # cuerpo
        body = QHBoxLayout()
        body.setSpacing(12)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(168)
        for name in ("🎬  Proyecto", "🥁  Ritmo y velocidad", "✨  Efectos", "🔤  Texto", "📤  Exportar"):
            self.nav.addItem(name)
        self.stack = QStackedWidget()
        self.stack.addWidget(scroll(self._page_project()))
        self.stack.addWidget(scroll(self._page_rhythm()))
        self.stack.addWidget(scroll(self._page_effects()))
        self.stack.addWidget(scroll(self._page_text()))
        self.stack.addWidget(scroll(self._page_export()))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        right = self._build_right()
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.stack)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        body.addWidget(self.nav)
        body.addWidget(split, 1)
        outer.addLayout(body, 1)

        # forma de onda + acciones
        self.wave = WaveformView()
        self.wave.startChanged.connect(self._wave_click)
        outer.addWidget(self.wave)
        bar = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFormat("Listo")
        self.btn_plan = QPushButton("📐 Planificar cortes")
        self.btn_prev = QPushButton("▶ Vista previa 8 s")
        self.btn_go = QPushButton("🔥 EXPORTAR REEL")
        self.btn_go.setObjectName("primary")
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setEnabled(False)
        bar.addWidget(self.progress, 1)
        for b in (self.btn_plan, self.btn_prev, self.btn_cancel, self.btn_go):
            bar.addWidget(b)
        outer.addLayout(bar)

        self.cmb_preset.activated.connect(self._preset_changed)
        self.btn_plan.clicked.connect(self.plan_cuts)
        self.btn_prev.clicked.connect(lambda: self.start_render(preview=True))
        self.btn_go.clicked.connect(lambda: self.start_render(preview=False))
        self.btn_cancel.clicked.connect(self.cancel_render)

        self.apply(apply_preset(Settings(), "Hype / Phonk"))
        self._startup_check()

    # ------------------------------------------------------------------ páginas
    def _page_project(self):
        c1 = Card("Videos de origen (uno o varios)")
        self.lst_videos = QListWidget()
        self.lst_videos.setMinimumHeight(170)
        self.lst_videos.setSelectionMode(QListWidget.ExtendedSelection)
        c1.add(self.lst_videos)
        h = QHBoxLayout()
        b1, b2, b3 = QPushButton("＋ Agregar videos"), QPushButton("Quitar"), QPushButton("Vaciar")
        b1.clicked.connect(self.add_videos)
        b2.clicked.connect(self.remove_videos)
        b3.clicked.connect(self.lst_videos.clear)
        for b in (b1, b2, b3):
            h.addWidget(b)
        h.addStretch(1)
        c1.addLayout(h)
        tip = QLabel("Tip: también puedes arrastrar y soltar videos y música sobre la ventana.")
        tip.setObjectName("muted")
        c1.add(tip)

        c2 = Card("Música / audio")
        h = QHBoxLayout()
        self.ed_audio = QLineEdit()
        self.ed_audio.setPlaceholderText("Selecciona un archivo de audio (mp3, wav, m4a…)")
        self.ed_audio.setReadOnly(True)
        bb = QPushButton("Examinar…")
        bb.clicked.connect(self.pick_audio)
        self.btn_analyze = QPushButton("🔍 Analizar")
        self.btn_analyze.clicked.connect(self.analyze_audio)
        h.addWidget(self.ed_audio, 1)
        h.addWidget(bb)
        h.addWidget(self.btn_analyze)
        c2.addLayout(h)
        self.lbl_audio = QLabel("Sin analizar")
        self.lbl_audio.setObjectName("muted")
        c2.add(self.lbl_audio)
        return page(c1, c2)

    def _page_rhythm(self):
        c1 = Card("Sincronización con la música")
        self.cmb_sync = combo(SYNC_MODES)
        c1.add(self.cmb_sync)
        self.sl_mincut = SliderRow("Corte mínimo (s)", 0.15, 1.5, 0.3, 0.05, "{:.2f}")
        self.sl_int = SliderRow("Intensidad general", 0.0, 1.0, 0.75, 0.05, "{:.2f}")
        c1.add(self.sl_mincut)
        c1.add(self.sl_int)
        h = QHBoxLayout()
        self.sp_dur = QDoubleSpinBox()
        self.sp_dur.setRange(3, 180)
        self.sp_dur.setSuffix(" s")
        self.sp_start = QDoubleSpinBox()
        self.sp_start.setRange(0, 3600)
        self.sp_start.setSuffix(" s")
        self.sp_start.setDecimals(2)
        self.cb_auto = QCheckBox("Buscar la mejor parte (drop)")
        h.addWidget(QLabel("Duración:"))
        h.addWidget(self.sp_dur)
        h.addWidget(QLabel("Inicio:"))
        h.addWidget(self.sp_start)
        h.addWidget(self.cb_auto)
        h.addStretch(1)
        c1.addLayout(h)

        c2 = Card("Curvas de velocidad automáticas")
        self.cb_speed = QCheckBox("Activar curvas de velocidad (speed ramps)")
        c2.add(self.cb_speed)
        self.grid_speed = CheckGrid(SPEED_KINDS, cols=1)
        c2.add(self.grid_speed)
        self.sl_speed = SliderRow("Intensidad de la curva", 0.0, 1.0, 0.6, 0.05)
        c2.add(self.sl_speed)
        self.cb_smooth = QCheckBox("Cámara lenta suave (mezcla de fotogramas, más lento)")
        c2.add(self.cb_smooth)
        self.curve = CurveView()
        c2.add(self.curve)
        self.grid_speed.changed.connect(self._update_curve)
        self.sl_speed.changed.connect(lambda _: self._update_curve())

        c3 = Card("Aleatoriedad")
        h = QHBoxLayout()
        self.sp_seed = QSpinBox()
        self.sp_seed.setRange(0, 999999)
        bd = QPushButton("🎲 Nuevo edit")
        bd.clicked.connect(lambda: self.sp_seed.setValue(random.randint(0, 999999)))
        h.addWidget(QLabel("Semilla:"))
        h.addWidget(self.sp_seed)
        h.addWidget(bd)
        h.addStretch(1)
        c3.addLayout(h)
        n = QLabel("La misma semilla + los mismos ajustes produce siempre el mismo edit.")
        n.setObjectName("muted")
        c3.add(n)
        return page(c1, c2, c3)

    def _grid_card(self, title, items, cols, attr):
        c = Card(title)
        g = CheckGrid(items, cols)
        setattr(self, attr, g)
        c.add(g)
        h = QHBoxLayout()
        a, n = QPushButton("Todos"), QPushButton("Ninguno")
        a.clicked.connect(lambda: g.set_all(True))
        n.clicked.connect(lambda: g.set_all(False))
        h.addWidget(a)
        h.addWidget(n)
        h.addStretch(1)
        c.addLayout(h)
        return c

    def _page_effects(self):
        cam = self._grid_card("Efectos de cámara", CAMERA_FX, 2, "grid_cam")
        lk = self._grid_card("Looks de color y arte (se reparten entre los cortes)", LOOKS, 2, "grid_look")
        self.cmb_lookmode = combo([("energy", "Según energía (suaves en calma, fuertes en drops)"),
                                   ("mix", "Mezclar al azar"), ("fixed", "Fijo (primer look marcado)")])
        lk.add(QLabel("Modo de reparto:"))
        lk.add(self.cmb_lookmode)
        tr = self._grid_card("Transiciones de cámara", TRANSITIONS, 3, "grid_trans")
        ac = self._grid_card("Acentos y fuego", ACCENTS, 2, "grid_acc")
        self.sl_fire = SliderRow("Cantidad de fuego", 0.0, 1.0, 0.55, 0.05)
        ac.add(self.sl_fire)
        return page(cam, lk, tr, ac)

    def _page_text(self):
        c = Card("Texto en pantalla (opcional)")
        self.cb_text = QCheckBox("Activar texto")
        c.add(self.cb_text)
        self.ed_text = QPlainTextEdit()
        self.ed_text.setPlaceholderText("Una frase por línea. En modo «palabras» salta una palabra por cada corte.")
        self.ed_text.setFixedHeight(100)
        c.add(self.ed_text)
        self.cmb_tmode = combo(TEXT_MODES)
        self.cmb_tstyle = combo(TEXT_STYLES)
        self.cmb_tpos = combo(TEXT_POS)
        for lab, w in (("Modo", self.cmb_tmode), ("Animación", self.cmb_tstyle), ("Posición", self.cmb_tpos)):
            h = QHBoxLayout()
            l = QLabel(lab)
            l.setMinimumWidth(90)
            h.addWidget(l)
            h.addWidget(w, 1)
            c.addLayout(h)
        self.sl_tsize = SliderRow("Tamaño", 40, 320, 150, 5, "{:.0f}")
        c.add(self.sl_tsize)
        h = QHBoxLayout()
        self.btn_tcolor = QPushButton("Color")
        self.btn_tcolor.clicked.connect(self.pick_color)
        self.btn_tfont = QPushButton("Fuente… (auto)")
        self.btn_tfont.clicked.connect(self.pick_font)
        self.cb_upper = QCheckBox("MAYÚSCULAS")
        h.addWidget(self.btn_tcolor)
        h.addWidget(self.btn_tfont)
        h.addWidget(self.cb_upper)
        h.addStretch(1)
        c.addLayout(h)
        return page(c)

    def _page_export(self):
        c = Card("Salida")
        self.cmb_res = combo(RESOLUTIONS)
        self.cmb_fps = combo([(24, "24 fps"), (30, "30 fps"), (60, "60 fps")])
        self.cmb_enc = combo([("libx264", "CPU (x264) — máxima compatibilidad"),
                              ("h264_nvenc", "GPU NVIDIA (NVENC) — más rápido")])
        self.sl_crf = SliderRow("Calidad (CRF, menor = mejor)", 12, 28, 17, 1, "{:.0f}")
        for lab, w in (("Resolución", self.cmb_res), ("Fotogramas", self.cmb_fps), ("Codificador", self.cmb_enc)):
            h = QHBoxLayout()
            l = QLabel(lab)
            l.setMinimumWidth(90)
            h.addWidget(l)
            h.addWidget(w, 1)
            c.addLayout(h)
        c.add(self.sl_crf)
        c2 = Card("Proyecto")
        h = QHBoxLayout()
        bs, bl = QPushButton("💾 Guardar proyecto"), QPushButton("📂 Cargar proyecto")
        bs.clicked.connect(self.save_project)
        bl.clicked.connect(self.load_project)
        h.addWidget(bs)
        h.addWidget(bl)
        h.addStretch(1)
        c2.addLayout(h)
        return page(c, c2)

    def _build_right(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        pc = Card("Vista previa")
        self.player = None
        if HAS_PLAYER:
            self.video = QVideoWidget()
            self.video.setMinimumSize(250, 360)
            self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.player = QMediaPlayer()
            self.aout = QAudioOutput()
            self.player.setAudioOutput(self.aout)
            self.player.setVideoOutput(self.video)
            pc.add(self.video)
            h = QHBoxLayout()
            bp, bs = QPushButton("▶ / ⏸"), QPushButton("⏹")
            bp.clicked.connect(self._toggle_play)
            bs.clicked.connect(self.player.stop)
            h.addWidget(bp)
            h.addWidget(bs)
            h.addStretch(1)
            pc.addLayout(h)
        else:
            self.lbl_prev = QLabel("La vista previa se abrirá en tu reproductor predeterminado.")
            self.lbl_prev.setWordWrap(True)
            pc.add(self.lbl_prev)
        v.addWidget(pc, 3)
        lc = Card("Registro")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        lc.add(self.log_view)
        v.addWidget(lc, 2)
        return w

    # ------------------------------------------------------------------ ajustes <-> UI
    def collect(self) -> Settings:
        s = Settings()
        s.preset = self.cmb_preset.currentData()
        s.sync_mode = self.cmb_sync.currentData()
        s.min_cut = self.sl_mincut.value()
        s.intensity = self.sl_int.value()
        s.duration, s.start, s.auto_window = self.sp_dur.value(), self.sp_start.value(), self.cb_auto.isChecked()
        s.speed_curves = self.cb_speed.isChecked()
        s.speed_kinds = self.grid_speed.checked()
        s.speed_amount = self.sl_speed.value()
        s.smooth_slowmo = self.cb_smooth.isChecked()
        s.seed = self.sp_seed.value()
        s.camera_fx = self.grid_cam.checked()
        s.looks = self.grid_look.checked()
        s.look_mode = self.cmb_lookmode.currentData()
        s.transitions = self.grid_trans.checked()
        s.accents = self.grid_acc.checked()
        s.fire_amount = self.sl_fire.value()
        s.text_enabled = self.cb_text.isChecked()
        s.text = self.ed_text.toPlainText()
        s.text_mode, s.text_style = self.cmb_tmode.currentData(), self.cmb_tstyle.currentData()
        s.text_pos = self.cmb_tpos.currentData()
        s.text_size = int(self.sl_tsize.value())
        s.text_color, s.text_font = self.text_color, self.text_font
        s.text_uppercase = self.cb_upper.isChecked()
        s.resolution = self.cmb_res.currentData()
        s.fps = int(self.cmb_fps.currentData())
        s.encoder = self.cmb_enc.currentData()
        s.crf = int(self.sl_crf.value())
        return s

    def apply(self, s: Settings):
        set_combo(self.cmb_preset, s.preset)
        set_combo(self.cmb_sync, s.sync_mode)
        self.sl_mincut.set_value(s.min_cut)
        self.sl_int.set_value(s.intensity)
        self.sp_dur.setValue(s.duration)
        self.sp_start.setValue(s.start)
        self.cb_auto.setChecked(s.auto_window)
        self.cb_speed.setChecked(s.speed_curves)
        self.grid_speed.set_checked(s.speed_kinds)
        self.sl_speed.set_value(s.speed_amount)
        self.cb_smooth.setChecked(s.smooth_slowmo)
        self.sp_seed.setValue(s.seed)
        self.grid_cam.set_checked(s.camera_fx)
        self.grid_look.set_checked(s.looks)
        set_combo(self.cmb_lookmode, s.look_mode)
        self.grid_trans.set_checked(s.transitions)
        self.grid_acc.set_checked(s.accents)
        self.sl_fire.set_value(s.fire_amount)
        self.cb_text.setChecked(s.text_enabled)
        self.ed_text.setPlainText(s.text)
        set_combo(self.cmb_tmode, s.text_mode)
        set_combo(self.cmb_tstyle, s.text_style)
        set_combo(self.cmb_tpos, s.text_pos)
        self.sl_tsize.set_value(s.text_size)
        self.text_color, self.text_font = s.text_color, s.text_font
        self._refresh_text_buttons()
        self.cb_upper.setChecked(s.text_uppercase)
        set_combo(self.cmb_res, s.resolution)
        set_combo(self.cmb_fps, s.fps)
        set_combo(self.cmb_enc, s.encoder)
        self.sl_crf.set_value(s.crf)
        self._update_curve()

    def _preset_changed(self, _):
        s = self.collect()
        keep = (s.duration, s.start, s.auto_window, s.seed, s.resolution, s.fps, s.crf, s.encoder,
                s.text_enabled, s.text, s.text_mode, s.text_style, s.text_pos, s.text_size, s.text_color,
                s.text_font, s.text_uppercase)
        apply_preset(s, self.cmb_preset.currentData())
        (s.duration, s.start, s.auto_window, s.seed, s.resolution, s.fps, s.crf, s.encoder, s.text_enabled,
         s.text, s.text_mode, s.text_style, s.text_pos, s.text_size, s.text_color, s.text_font,
         s.text_uppercase) = keep
        self.apply(s)
        self.log(f"Estilo «{s.preset}» aplicado.")

    def _update_curve(self):
        self.curve.set_data(self.grid_speed.checked(), 0.25 + 0.6 * self.sl_speed.value())

    def _refresh_text_buttons(self):
        self.btn_tcolor.setStyleSheet(f"border-left: 14px solid {self.text_color};")
        self.btn_tfont.setText("Fuente… (" + (os.path.basename(self.text_font) if self.text_font else "auto") + ")")

    # ------------------------------------------------------------------ acciones
    def log(self, msg: str):
        self.log_view.appendPlainText(msg)

    def _startup_check(self):
        try:
            ffutil.ffmpeg()
            cap = ffutil.capabilities()
            self.log(f"FFmpeg listo · {len(cap['filters'])} filtros · {len(cap['xfade'])} transiciones disponibles")
            if "h264_nvenc" not in cap["encoders"]:
                self.cmb_enc.setItemText(1, "GPU NVIDIA (NVENC) — no detectado")
        except Exception as e:
            QMessageBox.critical(self, "FFmpeg", str(e))

    def add_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Videos", "", "Videos (*" + " *".join(sorted(VIDEO_EXT)) + ")")
        self._add_video_paths(files)

    def _add_video_paths(self, paths):
        have = {self.lst_videos.item(i).data(Qt.UserRole) for i in range(self.lst_videos.count())}
        for p in paths:
            if p and p not in have:
                it = QListWidgetItem("🎞  " + os.path.basename(p))
                it.setData(Qt.UserRole, p)
                it.setToolTip(p)
                self.lst_videos.addItem(it)

    def remove_videos(self):
        for it in self.lst_videos.selectedItems():
            self.lst_videos.takeItem(self.lst_videos.row(it))

    def videos(self):
        return [self.lst_videos.item(i).data(Qt.UserRole) for i in range(self.lst_videos.count())]

    def pick_audio(self):
        f, _ = QFileDialog.getOpenFileName(self, "Audio", "", "Audio (*" + " *".join(sorted(AUDIO_EXT)) + ")")
        if f:
            self.set_audio(f)

    def set_audio(self, path):
        self.audio_path = path
        self.ed_audio.setText(path)
        self.an = None
        self.wave.set_analysis(None)
        self.analyze_audio()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        vids, aud = [], None
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            ext = os.path.splitext(p)[1].lower()
            if ext in VIDEO_EXT:
                vids.append(p)
            elif ext in AUDIO_EXT:
                aud = p
        self._add_video_paths(vids)
        if aud:
            self.set_audio(aud)

    def analyze_audio(self):
        if not self.audio_path:
            return self.pick_audio()
        self.btn_analyze.setEnabled(False)
        self.lbl_audio.setText("Analizando audio…")
        self.analyzer = AnalyzeWorker(self.audio_path)
        self.analyzer.done.connect(self._analysis_done)
        self.analyzer.failed.connect(self._analysis_failed)
        self.analyzer.start()

    def _analysis_done(self, an):
        self.an = an
        self.btn_analyze.setEnabled(True)
        self.lbl_audio.setText(f"{an.duration:.1f} s · {an.tempo:.1f} BPM · {len(an.beats)} beats · "
                               f"{len(an.onsets)} golpes detectados")
        self.wave.set_analysis(an)
        self._refresh_window()
        self.log(self.lbl_audio.text())

    def _analysis_failed(self, msg):
        self.btn_analyze.setEnabled(True)
        self.lbl_audio.setText("Error al analizar")
        QMessageBox.warning(self, "Audio", msg)

    def _refresh_window(self):
        if self.an:
            s = self.collect()
            a, b = engine.resolve_window(s, self.an)
            self.wave.set_window(a, b)

    def _wave_click(self, t):
        self.cb_auto.setChecked(False)
        self.sp_start.setValue(max(0.0, t))
        self._refresh_window()

    def plan_cuts(self):
        if not self.an:
            QMessageBox.information(self, "Cortes", "Primero carga y analiza un audio.")
            return
        s = self.collect()
        a, b = engine.resolve_window(s, self.an)
        plan = director.make_plan(s, self.an, a, b)
        self.wave.set_window(a, b)
        self.wave.set_plan(plan)
        kinds = {}
        for sg in plan.segs:
            kinds[sg.speed_kind] = kinds.get(sg.speed_kind, 0) + 1
        fires = sum(1 for sg in plan.segs if sg.fire)
        self.log(f"Plan: {len(plan.segs)} cortes entre {a:.1f}s y {b:.1f}s · curvas {kinds} · fuego en {fires}")

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.text_color), self, "Color del texto")
        if c.isValid():
            self.text_color = c.name()
            self._refresh_text_buttons()

    def pick_font(self):
        f, _ = QFileDialog.getOpenFileName(self, "Fuente", r"C:\Windows\Fonts" if os.name == "nt" else "",
                                           "Fuentes (*.ttf *.otf)")
        if f:
            self.text_font = f
            self._refresh_text_buttons()

    def save_project(self):
        f, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", "proyecto.reelforge", "ReelForge (*.reelforge)")
        if f:
            d = json.loads(self.collect().to_json())
            d["_videos"], d["_audio"] = self.videos(), self.audio_path
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh, indent=2, ensure_ascii=False)

    def load_project(self):
        f, _ = QFileDialog.getOpenFileName(self, "Cargar proyecto", "", "ReelForge (*.reelforge)")
        if not f:
            return
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        self.apply(Settings.from_dict(d))
        self.lst_videos.clear()
        self._add_video_paths([p for p in d.get("_videos", []) if os.path.exists(p)])
        if d.get("_audio") and os.path.exists(d["_audio"]):
            self.set_audio(d["_audio"])

    # ------------------------------------------------------------------ render
    def _busy(self, on: bool):
        for b in (self.btn_go, self.btn_prev, self.btn_plan):
            b.setEnabled(not on)
        self.btn_cancel.setEnabled(on)

    def start_render(self, preview: bool):
        vids = self.videos()
        if not vids:
            QMessageBox.information(self, "Videos", "Agrega al menos un video.")
            return
        if not self.audio_path:
            QMessageBox.information(self, "Audio", "Selecciona un audio.")
            return
        s = self.collect()
        s.preview = preview
        if preview:
            out = os.path.join(engine.cache_dir(), "preview.mp4")
        else:
            out, _ = QFileDialog.getSaveFileName(self, "Guardar reel", "reel.mp4", "MP4 (*.mp4)")
            if not out:
                return
        self.last_out = out
        self._busy(True)
        self._t0 = time.time()
        self.worker = RenderWorker(s, vids, self.audio_path, out, self.an)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self.log)
        self.worker.done.connect(lambda p: self._render_done(p, preview))
        self.worker.failed.connect(self._render_failed)
        self.worker.start()

    def cancel_render(self):
        if self.worker:
            self.worker.stop()
            self.progress.setFormat("Cancelando…")

    def _on_progress(self, f, msg):
        self.progress.setValue(int(f * 1000))
        el = time.time() - self._t0
        eta = f" · ~{int(el / f - el)} s restantes" if f > 0.08 else ""
        self.progress.setFormat(f"{msg}  {f * 100:.0f}%{eta}")

    def _render_done(self, path, preview):
        self._busy(False)
        self.progress.setValue(1000)
        self.progress.setFormat("Listo ✔")
        if self.an is None and self.audio_path:
            self.analyze_audio()
        if preview:
            self._play(path)
        else:
            self.log(f"Reel exportado en {path}")
            if QMessageBox.question(self, "Listo", f"Reel exportado:\n{path}\n\n¿Abrir carpeta?") == QMessageBox.Yes:
                self._reveal(path)
            self._play(path)

    def _render_failed(self, msg):
        self._busy(False)
        self.progress.setFormat("Error")
        self.log("✖ " + msg)
        if msg != "Cancelado.":
            QMessageBox.critical(self, "Error de render", msg[-1200:])

    def _reveal(self, path):
        try:
            if os.name == "nt":
                os.startfile(os.path.dirname(path))  # type: ignore[attr-defined]
        except Exception:
            pass

    def _play(self, path):
        if self.player:
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def _toggle_play(self):
        if not self.player:
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()
