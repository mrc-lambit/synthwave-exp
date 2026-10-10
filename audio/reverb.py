from typing import List

import numpy as np


class SchroederReverb:
    """Mono Schroeder reverb with parallel feedback combs and serial all-passes."""

    COMB_DELAYS_MS = (29.7, 37.1, 41.1, 43.7)
    ALLPASS_DELAYS_MS = (5.0, 1.7)
    ALLPASS_FEEDBACK = 0.7

    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = int(sample_rate)
        self.enabled = False
        self.decay_seconds = 1.8
        self.mix = 0.3
        self._comb_delays = [
            max(1, int(round(self.sample_rate * delay_ms / 1000.0)))
            for delay_ms in self.COMB_DELAYS_MS
        ]
        self._allpass_delays = [
            max(1, int(round(self.sample_rate * delay_ms / 1000.0)))
            for delay_ms in self.ALLPASS_DELAYS_MS
        ]
        self._comb_buffers: List[np.ndarray] = [
            np.zeros(delay, dtype=np.float32) for delay in self._comb_delays
        ]
        self._allpass_buffers: List[np.ndarray] = [
            np.zeros(delay, dtype=np.float32) for delay in self._allpass_delays
        ]
        self._comb_indices = [0] * len(self._comb_buffers)
        self._allpass_indices = [0] * len(self._allpass_buffers)
        self._update_feedback()

    def set_parameters(
        self,
        enabled: bool,
        decay_seconds: float = 1.8,
        mix: float = 0.3,
    ) -> None:
        self.enabled = bool(enabled)
        self.decay_seconds = float(np.clip(decay_seconds, 0.3, 5.0))
        self.mix = float(np.clip(mix, 0.0, 1.0))
        self._update_feedback()

    def _update_feedback(self) -> None:
        delay_seconds = np.asarray(self._comb_delays, dtype=np.float64) / self.sample_rate
        self._comb_feedback = np.power(10.0, -3.0 * delay_seconds / self.decay_seconds)

    def process(self, samples: np.ndarray) -> np.ndarray:
        if not self.enabled:
            self.reset()
            return samples

        wet = np.empty_like(samples)
        minimum_delay = min(self._comb_delays + self._allpass_delays)
        remaining = len(samples)
        input_index = 0

        while remaining:
            block_size = min(remaining, minimum_delay)
            offsets = np.arange(block_size, dtype=np.int64)
            input_block = samples[input_index:input_index + block_size]
            comb_sum = np.zeros(block_size, dtype=np.float32)

            for index, buffer in enumerate(self._comb_buffers):
                positions = (self._comb_indices[index] + offsets) % len(buffer)
                delayed = buffer[positions].copy()
                comb_sum += delayed
                buffer[positions] = input_block + delayed * self._comb_feedback[index]
                self._comb_indices[index] = (
                    self._comb_indices[index] + block_size
                ) % len(buffer)

            stage = comb_sum * (1.0 / len(self._comb_buffers))
            for index, buffer in enumerate(self._allpass_buffers):
                positions = (self._allpass_indices[index] + offsets) % len(buffer)
                delayed = buffer[positions].copy()
                output = delayed - self.ALLPASS_FEEDBACK * stage
                buffer[positions] = stage + self.ALLPASS_FEEDBACK * output
                self._allpass_indices[index] = (
                    self._allpass_indices[index] + block_size
                ) % len(buffer)
                stage = output

            wet[input_index:input_index + block_size] = stage
            input_index += block_size
            remaining -= block_size

        return samples * (1.0 - self.mix) + wet * self.mix

    def reset(self) -> None:
        for buffer in self._comb_buffers + self._allpass_buffers:
            buffer.fill(0.0)
        self._comb_indices = [0] * len(self._comb_buffers)
        self._allpass_indices = [0] * len(self._allpass_buffers)
