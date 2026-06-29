"""Simple digital filters for the synth prototype."""
from __future__ import annotations

import numpy as np


class Filter:
    """A minimal one-pole filter implementation for LP/HP/BP."""

    def __init__(self, kind: str = "lowpass", cutoff: float = 2000.0, resonance: float = 0.0) -> None:
        self.kind = kind.lower()
        self.cutoff = cutoff
        self.resonance = resonance
        self.previous = 0.0

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Filter each sample using a simple first-order approximation."""
        output = np.empty_like(samples, dtype=np.float32)
        alpha = min(0.99, max(0.01, 1.0 - (self.cutoff / sample_rate)))
        for index, sample in enumerate(samples):
            if self.kind == "lowpass":
                filtered = self.previous + alpha * (sample - self.previous)
            elif self.kind == "highpass":
                filtered = alpha * (self.previous + sample - self.previous)
            else:
                filtered = sample
            output[index] = filtered
            self.previous = filtered
        return output
