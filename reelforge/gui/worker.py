"""Hilos de trabajo para no bloquear la interfaz."""
from __future__ import annotations
import threading, traceback
from PySide6.QtCore import QThread, Signal
from .. import audio, engine
from ..ffutil import Cancelled


class AnalyzeWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            self.done.emit(audio.analyze(self.path))
        except Exception as e:  # noqa
            self.failed.emit(str(e))


class RenderWorker(QThread):
    progress = Signal(float, str)
    log = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, videos, audio_path, out_path, analysis=None):
        super().__init__()
        self.s, self.videos, self.audio_path, self.out_path, self.an = settings, videos, audio_path, out_path, analysis
        self.cancel = threading.Event()

    def stop(self):
        self.cancel.set()

    def run(self):
        try:
            engine.render(self.s, self.videos, self.audio_path, self.out_path,
                          progress=lambda f, m="": self.progress.emit(f, m),
                          log=lambda m: self.log.emit(m), cancel=self.cancel,
                          analysis_cache=self.an)
            self.done.emit(self.out_path)
        except Cancelled:
            self.failed.emit("Cancelado.")
        except Exception as e:  # noqa
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(e))
