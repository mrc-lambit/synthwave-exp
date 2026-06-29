"""Main application window for the synthesizer prototype."""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from audio.engine import AudioEngine
from audio.oscillator import Oscillator
from audio.voice import Voice


class MainWindow(QWidget):
    """Minimal Qt window that wires the audio engine to the GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Software Synth Prototype")
        self.resize(480, 240)

        self.engine = AudioEngine()
        self.voice = Voice(self.engine.sample_rate, Oscillator("sine", 440.0, 0.25))
        self.engine.mixer.add_voice(self.voice)

        self.status_label = QLabel("Audio engine ready")
        self.start_button = QPushButton("Start Audio")
        self.start_button.clicked.connect(self.start_audio)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Synth Prototype"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)

    def start_audio(self) -> None:
        """Start the audio engine and update the UI."""
        self.engine.start()
        self.status_label.setText("Audio engine running")


def main() -> None:
    """Run the application from this module."""
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
