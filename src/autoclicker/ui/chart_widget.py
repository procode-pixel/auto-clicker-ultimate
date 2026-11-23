"""Session bar chart."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class SessionChart(QWidget):
    def __init__(self):
        super().__init__()
        self._values: list[int] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, values: list[int]) -> None:
        self._values = [max(0, int(v)) for v in values][-24:]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -22)
        if not self._values or max(self._values) == 0:
            painter.setPen(QColor(160, 168, 180))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No sessions to chart yet")
            painter.end()
            return
        peak = max(self._values)
        gap = 4
        count = len(self._values)
        width = max(4, (rect.width() - gap * (count - 1)) // count)
        accent = QColor(88, 166, 255)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, value in enumerate(self._values):
            height = max(1, int(rect.height() * (value / peak)))
            x = rect.left() + index * (width + gap)
            bar = rect.adjusted(0, rect.height() - height, 0, 0)
            bar.setLeft(x)
            bar.setWidth(width)
            painter.fillRect(bar, accent)
        painter.setPen(QPen(QColor(140, 148, 160)))
        painter.drawText(8, self.height() - 6, f"Last {count} sessions, peak {peak}")
        painter.end()
