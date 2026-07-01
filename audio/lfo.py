# -*- coding: utf-8 -*-
"""Simple low-frequency oscillator for modulation."""

import numpy as np


class LFO:
    """Generate a periodic modulation signal for pitch, volume, or filter."""

    def __init__(
        self,
        sample_rate: int = 44100,
        frequency: float = 0.0,
        depth: float = 0.0,
        waveform: str = "sine",
    ) -> None:
        self.sample_rate = sample_rate
        self.frequency = max(0.0, float(frequency))
        self.depth = max(0.0, float(depth))
        self.waveform = waveform.lower()
        self.phase = 0.0

    def set_parameters(self, frequency: float = 0.0, depth: float = 0.0) -> None:
        self.frequency = max(0.0, float(frequency))
        self.depth = max(0.0, float(depth))

    def _evaluate_phase(self, phase: float) -> float:
        if self.waveform == "square":
            return 1.0 if phase < 0.5 else -1.0
        if self.waveform == "triangle":
            return 4.0 * phase - 1.0 if phase < 0.5 else 3.0 - 4.0 * phase
        if self.waveform == "sawtooth":
            return 2.0 * phase - 1.0
        return float(np.sin(2.0 * np.pi * phase))

    def get_value(self) -> float:
        """Return the current LFO value without advancing the phase."""
        if self.frequency <= 0.0 or self.depth <= 0.0:
            return 0.0
        return self._evaluate_phase(self.phase)

    def generate(self, num_samples: int) -> np.ndarray:
        """Generate a buffer of modulation values."""
        if self.frequency <= 0.0 or self.depth <= 0.0:
            return np.zeros(num_samples, dtype=np.float32)

        phase_increment = self.frequency / self.sample_rate
        phases = np.arange(num_samples, dtype=np.float32) * phase_increment + self.phase
        phases = np.mod(phases, 1.0)

        values = np.array([self._evaluate_phase(p) for p in phases], dtype=np.float32)
        self.phase = phases[-1] + phase_increment
        self.phase = np.mod(self.phase, 1.0)

        return values * self.depth
