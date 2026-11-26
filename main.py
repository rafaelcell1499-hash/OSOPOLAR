import os, sys

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from reelforge.gui.theme import QSS
    from reelforge.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
