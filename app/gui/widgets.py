"""Custom widgets for Airpoint GUI."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtWidgets import QLabel


class StatusIndicator(QLabel):
    """Colored status indicator dot."""

    def __init__(self, color: str = "gray", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(12, 12)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = QColor(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 12, 12)
        painter.end()


class GestureDisplay(QLabel):
    """Displays current detected gesture."""

    def __init__(self, parent=None):
        super().__init__("No gesture detected", parent)
        self.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #4CAF50;
            padding: 8px;
        """)
        self.setMinimumHeight(40)
        self.setAlignment(Qt.AlignCenter)

    def update_gesture(self, gesture: str):
        self.setText(gesture)
