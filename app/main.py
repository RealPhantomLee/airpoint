"""Airpoint - Touchless Cursor Control.

Main entry point for the application.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from app.config import Settings
from app.control.mouse import MouseController
from app.gui.window import MainWindow


def main():
    """Application entry point."""
    # Load settings
    settings = Settings()

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Airpoint")
    app.setOrganizationName("Airpoint")

    # Create mouse controller
    mouse_controller = MouseController(settings)
    mouse_controller.set_paused(True)

    # Create and show main window
    window = MainWindow(settings, mouse_controller)
    window.show()

    # Run
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
