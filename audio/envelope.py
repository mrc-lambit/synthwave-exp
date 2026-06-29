"""ADSR envelope utilities for voice amplitude shaping."""
from __future__ import annotations

import numpy as np


class ADSREnvelope:
    """Simple ADSR generator over a duration in samples."""

    def __init__(self, attack: float = 0.01, decay: float = 0.1, sustain: float = 0.7, release: float = 0.2) -> None:
        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release

    def generate(self, sample_rate: int, num_samples: int, note_on: bool = True) -> np.ndarray:
        """Generate envelope values for a block of samples."""
        envelope = np.ones(num_samples, dtype=np.float32)
        attack_samples = max(1, int(self.attack * sample_rate))
        decay_samples = max(1, int(self.decay * sample_rate))
        release_samples = max(1, int(self.release * sample_rate))

        if note_on:
            envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)
            if num_samples > attack_samples:
                envelope[attack_samples:attack_samples + decay_samples] = np.linspace(1.0, self.sustain, min(decay_samples, num_samples - attack_samples), dtype=np.float32)
            if num_samples > attack_samples + decay_samples:
                envelope[attack_samples + decay_samples:] = self.sustain
        else:
            envelope[:release_samples] = np.linspace(self.sustain, 0.0, release_samples, dtype=np.float32)
            envelope[release_samples:] = 0.0

        return envelope
