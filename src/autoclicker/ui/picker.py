"""Fullscreen coordinate picker. It closes as soon as the user clicks once."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QLabel, QWidget


class PointPicker(QWidget):
    picked = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowOpacity(0.28)
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        label = QLabel("Click the target point. Press Esc to cancel.", self)
        label.setStyleSheet("font-size: 22px; font-weight: 700;")
        label.move(48, 48)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        point = event.globalPosition().toPoint()
        self.picked.emit(point.x(), point.y())
        self.close()

    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.close()
