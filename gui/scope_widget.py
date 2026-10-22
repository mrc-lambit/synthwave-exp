from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
import numpy as np

class ScopeWidget(QWidget):
    """3-mode Widget: Oscilloscope, Linear dB FFT, Logarithmic FFT Spectrum."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        # Buffer esteso a 2048 campioni per maggiore risoluzione in frequenza
        self.fft_size = 2048
        self.samples = np.zeros(self.fft_size, dtype=np.float32)
        
        # Modalità: "oscilloscope", "fft_db", "fft_log"
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
            self.samples = np.pad(arr, (0, self.fft_size - len(arr)))
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            modes = ["oscilloscope", "fft_db", "fft_log"]
            next_idx = (modes.index(self.mode) + 1) % len(modes)
            self.mode = modes[next_idx]
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
        elif self.mode == "fft_db":
            self._draw_fft_db(painter, width, height)
        elif self.mode == "fft_log":
            self._draw_fft_log(painter, width, height)

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

    def _draw_fft_db(self, painter: QPainter, width: int, height: int) -> None:
        """FFT in Decibel (dB) su scala di frequenza lineare."""
        windowed_samples = self.samples * self.window
        
        # FFT reale
        fft_data = np.abs(np.fft.rfft(windowed_samples))
        
        # Usiamo solo la metà inferiore dello spettro (focus sulle frequenze udibili)
        num_bins = len(fft_data) // 2
        fft_data = fft_data[:num_bins]
        
        if num_bins == 0:
            return

        # Calcolo ampiezza reale in dB
        fft_norm = fft_data / max(num_bins, 1.0)
        fft_db = 20 * np.log10(np.maximum(fft_norm, 1e-6))
        spectrum = np.clip((fft_db + 80) / 80, 0, 1)

        pen = QPen(QColor("#ff5577"))
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

    def _draw_fft_log(self, painter: QPainter, width: int, height: int) -> None:
        """FFT in Decibel (dB) su scala di frequenza logaritmica."""
        sample_rate = 44100
        windowed_samples = self.samples * self.window
        fft_data = np.abs(np.fft.rfft(windowed_samples))

        num_bins = len(fft_data) // 2
        fft_data = fft_data[1:num_bins]
        if len(fft_data) == 0:
            return

        fft_norm = fft_data / max(len(fft_data), 1.0)
        fft_db = 20 * np.log10(np.maximum(fft_norm, 1e-6))
        spectrum = np.clip((fft_db + 80) / 80, 0, 1)

        # Griglia di riferimento frequenze Hz
        freq_markers = [50, 100, 500, 1000, 5000, 10000]
        max_freq = sample_rate / 4.0
        log_min = np.log10(1)
        log_max = np.log10(len(spectrum))

        painter.setPen(QPen(QColor("#1f2d48"), 1, Qt.PenStyle.DashLine))
        painter.setFont(self.font())

        for freq in freq_markers:
            if freq < max_freq:
                bin_idx = (freq / (sample_rate / 2.0)) * len(fft_data)
                if bin_idx >= 1:
                    log_pos = (np.log10(bin_idx) - log_min) / (log_max - log_min)
                    x = int(log_pos * width)
                    painter.drawLine(x, 25, x, height)

                    label = f"{freq if freq < 1000 else f'{freq//1000}k'}"
                    painter.setPen(QColor("#4c5cff"))
                    painter.drawText(x + 2, height - 6, label)
                    painter.setPen(QPen(QColor("#1f2d48"), 1, Qt.PenStyle.DashLine))

        # Curva FFT Logaritmica
        pen = QPen(QColor("#56e0c2"))
        pen.setWidth(1)
        painter.setPen(pen)

        prev_x, prev_y = None, None
        for i in range(len(spectrum)):
            log_pos = (np.log10(i + 1) - log_min) / (log_max - log_min)
            x = int(log_pos * width)
            y = int(height - (spectrum[i] * (height * 0.8)))

            if prev_x is not None:
                painter.drawLine(prev_x, prev_y, x, y)

            prev_x, prev_y = x, y

        painter.setPen(QColor("#a0a0a0"))
        painter.drawText(8, 18, f"FFT Log ({len(spectrum)} bins)")