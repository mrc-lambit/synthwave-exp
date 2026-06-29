"""A single synth voice that can be rendered into audio blocks."""
from __future__ import annotations

import numpy as np

from .oscillator import Oscillator


class Voice:
    """Represents a single note being played by the synthesizer."""

    def __init__(self, sample_rate: int, oscillator: Oscillator | None = None) -> None:
        self.sample_rate = sample_rate
        self.oscillator = oscillator or Oscillator("sine", 440.0, 0.25)
        self.frequency = 440.0
        self.phase = 0.0
        self.amplitude = 0.0
        self.active = False
        self.release_level = 0.0

    def note_on(self, frequency: float, amplitude: float = 0.25) -> None:
        """Start a new note with the requested frequency and amplitude."""
        self.frequency = frequency
        self.amplitude = amplitude
        self.active = True
        self.release_level = amplitude

    def note_off(self) -> None:
        """Stop the note and begin release phase."""
        self.active = False

    def render(self, num_samples: int) -> np.ndarray:
        """Render a block of samples for this voice."""
        if not self.active:
            return np.zeros(num_samples, dtype=np.float32)

        samples = self.oscillator.generate(self.sample_rate, num_samples, self.phase)
        self.phase += 2.0 * np.pi * self.frequency / self.sample_rate
        return samples * self.amplitude
