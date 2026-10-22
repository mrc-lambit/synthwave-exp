from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
import numpy as np

class ScopeWidget(QWidget):
    """Oscilloscope and high-detail FFT spectrum widget for audio samples."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        # Buffer esteso a 2048 campioni per maggiore risoluzione in frequenza
        self.fft_size = 2048
        self.samples = np.zeros(self.fft_size, dtype=np.float32)
        self.mode = "oscilloscope"
        # Precalcolo della finestra di Hann per la FFT
        self.window = np.hanning(self.fft_size)
        self.setStyleSheet("background-color: #060816; border-radius: 6px;")

    def set_samples(self, samples: np.ndarray) -> None:
        if samples is None or len(samples) == 0:
            return
        arr = np.asarray(samples, dtype=np.float32)
        if len(arr) >= self.fft_size:
            self.samples = arr[:self.fft_size]
        else:
            # Padding se i campioni in ingresso sono inferiori
            self.samples = np.pad(arr, (0, self.fft_size - len(arr)))
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.mode = "spectrum" if self.mode == "oscilloscope" else "oscilloscope"
            self.update()
            event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#060816"))

        width = self.width()
        height = self.height()

        if len(self.samples) < 2:
            return

        if self.mode == "oscilloscope":
            self._draw_oscilloscope(painter, width, height)
        else:
            self._draw_spectrum(painter, width, height)

    def _draw_oscilloscope(self, painter: QPainter, width: int, height: int) -> None:
        pen = QPen(QColor("#4c5cff"))
        pen.setWidth(2)
        painter.setPen(pen)

        # Per l'oscilloscopio visualizziamo solo i primi 512 campioni per chiarezza visiva
        values = self.samples[:512]
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

        painter.setPen(QColor("#a0a0a0"))
        painter.drawText(8, 18, "Oscilloscope")

    def _draw_spectrum(self, painter: QPainter, width: int, height: int) -> None:
        # Finestra di Hann sui campioni per eliminare artefatti ai bordi
        windowed_samples = self.samples * self.window
        
        # FFT reale
        fft_data = np.abs(np.fft.rfft(windowed_samples))
        
        # Usiamo solo la metà inferiore dello spettro (focus sulle frequenze udibili)
        num_bins = len(fft_data) // 2
        fft_data = fft_data[:num_bins]
        
        if num_bins == 0:
            return

        # Normalizzazione in dB con dinamica estesa
        fft_norm = fft_data / max(num_bins, 1.0)
        fft_db = 20 * np.log10(np.maximum(fft_norm, 1e-6))
        spectrum = np.clip((fft_db + 80) / 80, 0, 1)

        pen = QPen(QColor("#56e0c2"))
        pen.setWidth(1)
        painter.setPen(pen)

        for index in range(1, num_bins):
            x1 = (index - 1) / max(1, num_bins - 1) * width
            y1 = height - (spectrum[index - 1] * (height * 0.85))
            x2 = index / max(1, num_bins - 1) * width
            y2 = height - (spectrum[index] * (height * 0.85))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        painter.setPen(QColor("#a0a0a0"))
        painter.drawText(8, 18, f"FFT Spectrum ({num_bins} bins)")