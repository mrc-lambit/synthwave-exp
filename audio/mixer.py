"""Mixer for combining rendered voices into a final stereo-ish signal."""
from __future__ import annotations

import numpy as np


class Mixer:
    """Mix multiple voices into one audio buffer."""

    def __init__(self) -> None:
        self.voices: list = []

    def add_voice(self, voice) -> None:
        """Register a voice with the mixer."""
        self.voices.append(voice)

    def render(self, num_samples: int) -> np.ndarray:
        """Render all active voices into a single output buffer."""
        output = np.zeros(num_samples, dtype=np.float32)
        for voice in self.voices:
            output += voice.render(num_samples)
        return np.clip(output, -1.0, 1.0)
