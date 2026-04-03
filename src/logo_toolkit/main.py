from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from logo_toolkit.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Logo Toolkit")
    window = MainWindow()
    window.show()
    return app.exec()
