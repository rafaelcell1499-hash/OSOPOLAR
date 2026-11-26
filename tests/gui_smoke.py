"""Prueba de humo de la GUI (offscreen): crea ventana, analiza audio, planifica y captura imagen."""
import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
from reelforge.gui.theme import QSS
from reelforge.gui.main_window import MainWindow

app = QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(QSS)
w = MainWindow(); w.show()
vids = sys.argv[2:] if len(sys.argv) > 2 else []
w._add_video_paths(vids)
w.set_audio(sys.argv[1])
t = time.time()
while w.an is None and time.time() - t < 60:
    app.processEvents(); time.sleep(0.05)
assert w.an is not None, "analysis failed"
w.plan_cuts()
w.nav.setCurrentRow(2)
app.processEvents()
out = os.environ.get("SHOT", "gui.png")
w.grab().save(out)
print("OK", out, w.collect().preset)
