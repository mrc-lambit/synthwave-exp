from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor
import numpy as np


class ScopeWidget(QWidget):
    """A minimal oscilloscope widget for rendering audio waveform samples."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.samples = np.zeros(512, dtype=np.float32)
        self.setStyleSheet("background-color: #060816; border-radius: 6px;")

    def set_samples(self, samples: np.ndarray) -> None:
        if samples is None or len(samples) == 0:
            return
        self.samples = np.asarray(samples, dtype=np.float32)[:512]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.fillRect(self.rect(), QColor("#060816"))

        pen = QPen(QColor("#4c5cff"))
        pen.setWidth(2)
        painter.setPen(pen)

        width = self.width()
        height = self.height()
        if len(self.samples) < 2:
            return

        values = self.samples
        if len(values) != width:
            step = max(1, len(values) // max(1, width))
            values = values[::step]
            if len(values) > width:
                values = values[:width]

        center_y = height / 2.0
        for index in range(1, len(values)):
            x1 = (index - 1) / max(1, len(values) - 1) * width
            y1 = center_y - values[index - 1] * (height * 0.4)
            x2 = index / max(1, len(values) - 1) * width
            y2 = center_y - values[index] * (height * 0.4)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
