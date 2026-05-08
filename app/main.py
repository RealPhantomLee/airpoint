"""Airpoint — Touchless interaction framework.

Entry point. The MainWindow owns the rest of the dependency graph
(MouseController, MediaController, ModeManager, GestureClassifier,
ActionDispatcher, Pipeline), so this stays small.
"""

from __future__ import annotations

import os
import sys

# Make the project root importable when running as `python -m app.main` or
# directly via `python app/main.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from app.config import Settings
from app.gui.main_window import MainWindow


def main() -> int:
    settings = Settings()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName("Airpoint")
    app.setOrganizationName("Airpoint")
    app.setQuitOnLastWindowClosed(False)  # tray keeps app alive when window hidden

    window = MainWindow(settings)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
