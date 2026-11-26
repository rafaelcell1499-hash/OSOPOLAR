"""Tema oscuro profesional (QSS)."""

BG = "#0d0e13"
PANEL = "#151720"
PANEL2 = "#1b1e29"
BORDER = "#262a38"
TEXT = "#e9eaf0"
MUTED = "#8a90a6"
ACCENT = "#ff6a1f"
ACCENT2 = "#ffb21f"
GOOD = "#3ddc97"

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#cardTitle {{ color: {ACCENT2}; font-weight: 700; font-size: 12px; letter-spacing: 1px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#logo {{ font-size: 22px; font-weight: 800; color: {ACCENT}; }}
QLabel#h1 {{ font-size: 18px; font-weight: 700; }}
QListWidget#nav {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; padding: 6px; outline: 0; }}
QListWidget#nav::item {{ padding: 11px 14px; border-radius: 8px; margin: 2px 0; color: {MUTED}; }}
QListWidget#nav::item:selected {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: #14110d; font-weight: 700; }}
QListWidget#nav::item:hover:!selected {{ background: {PANEL2}; color: {TEXT}; }}
QListWidget {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 5px; border-radius: 6px; }}
QListWidget::item:selected {{ background: #2a2f42; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #555a6b; }}
QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: #14110d; font-weight: 800; border: none; padding: 11px 22px; font-size: 14px; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff7f3a, stop:1 #ffc24a); }}
QPushButton#primary:disabled {{ background: #3a3d4a; color: #777; }}
QPushButton#danger {{ border-color: #6b2b2b; color: #ff7b7b; }}
QCheckBox {{ spacing: 8px; padding: 3px 0; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border-radius: 5px; border: 1px solid #3a3f55; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QPlainTextEdit {{ background: {PANEL2}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 6px 8px; selection-background-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QSlider::groove:horizontal {{ height: 6px; background: #262a38; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2}); border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: #fff; }}
QProgressBar {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; height: 18px; text-align: center; }}
QProgressBar::chunk {{ border-radius: 7px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2}); }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #2d3246; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {ACCENT}; }}
QSplitter::handle {{ background: transparent; }}
"""
