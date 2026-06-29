"""Real-time audio engine based on sounddevice."""
from __future__ import annotations

import numpy as np
import sounddevice as sd

from .mixer import Mixer


class AudioEngine:
    """A simple asynchronous audio engine that streams generated samples."""

    def __init__(self, sample_rate: int = 44100, block_size: int = 256) -> None:
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.mixer = Mixer()
        self.stream = None
        self.running = False

    def start(self) -> None:
        """Start the audio stream."""
        if self.running:
            return
        self.stream = sd.OutputStream(samplerate=self.sample_rate, blocksize=self.block_size, channels=1, callback=self._callback)
        self.stream.start()
        self.running = True

    def stop(self) -> None:
        """Stop the audio stream."""
        if not self.running:
            return
        self.stream.stop()
        self.stream.close()
        self.running = False

    def _callback(self, outdata, frames, time_info, status) -> None:
        """Generate and write audio data for the callback."""
        if status:
            print(status)
        data = self.mixer.render(frames)
        outdata[:, 0] = data
        if data.shape[0] < frames:
            outdata[data.shape[0]:, 0] = 0.0
