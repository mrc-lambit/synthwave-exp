from __future__ import annotations

import numpy as np


class Filter:
    """Topology-preserving state-variable filter with low/high/band-pass modes."""

    MIN_CUTOFF_HZ = 20.0
    MAX_RESONANCE_Q = 10.0
    MIN_RESONANCE_Q = 1.0 / np.sqrt(2.0)

    def __init__(
        self,
        kind: str = "lowpass",
        cutoff: float = 2000.0,
        resonance: float = 0.0,
    ) -> None:
        self.kind = kind.lower()
        self.cutoff = float(cutoff)
        self.resonance = float(np.clip(resonance, 0.0, 1.0))
        self._integrator_1 = 0.0
        self._integrator_2 = 0.0

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        """Filter a block while preserving integrator state between blocks."""
        output = np.empty_like(samples, dtype=np.float32)
        if samples.size == 0:
            return output

        cutoff = float(np.clip(
            self.cutoff,
            self.MIN_CUTOFF_HZ,
            sample_rate * 0.45,
        ))
        q = self.MIN_RESONANCE_Q + self.resonance * (
            self.MAX_RESONANCE_Q - self.MIN_RESONANCE_Q
        )
        damping = 1.0 / q
        g = float(np.tan(np.pi * cutoff / sample_rate))
        a1 = 1.0 / (1.0 + g * (g + damping))
        a2 = g * a1
        a3 = g * a2

        integrator_1 = self._integrator_1
        integrator_2 = self._integrator_2
        if self.kind == "lowpass":
            for index, sample in enumerate(samples):
                band = a2 * (sample - integrator_2) + a1 * integrator_1
                low = integrator_2 + a2 * integrator_1 + a3 * (
                    sample - integrator_2
                )
                integrator_1 = 2.0 * band - integrator_1
                integrator_2 = 2.0 * low - integrator_2
                output[index] = low
        elif self.kind == "highpass":
            for index, sample in enumerate(samples):
                band = a2 * (sample - integrator_2) + a1 * integrator_1
                low = integrator_2 + a2 * integrator_1 + a3 * (
                    sample - integrator_2
                )
                high = sample - damping * band - low
                integrator_1 = 2.0 * band - integrator_1
                integrator_2 = 2.0 * low - integrator_2
                output[index] = high
        elif self.kind == "bandpass":
            for index, sample in enumerate(samples):
                band = a2 * (sample - integrator_2) + a1 * integrator_1
                low = integrator_2 + a2 * integrator_1 + a3 * (
                    sample - integrator_2
                )
                integrator_1 = 2.0 * band - integrator_1
                integrator_2 = 2.0 * low - integrator_2
                output[index] = band
        else:
            output[:] = samples
            return output

        self._integrator_1 = integrator_1
        self._integrator_2 = integrator_2
        return output
