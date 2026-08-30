# -*- coding: utf-8 -*-
"""
Envelope module for the MUSA software synthesizer.

Implements ADSR (Attack, Decay, Sustain, Release) envelope.
This shapes the amplitude of a note over time, preventing clicks and enabling
natural-sounding note articulation.

ADSR Envelope Stages:
1. ATTACK:  Ramp from 0 to peak (1.0) over attack_time
2. DECAY:   Ramp from peak to sustain level over decay_time
3. SUSTAIN: Hold at sustain level while note is held
4. RELEASE: Ramp from sustain level to 0 over release_time after note off

Formula: envelope_output = current_amplitude * oscillator_output
"""

from enum import Enum
from typing import Optional

import numpy as np


class EnvelopeStage(Enum):
    """Enumeration of ADSR envelope stages."""
    
    ATTACK = 1    # Rising from 0 to peak
    DECAY = 2     # Falling from peak to sustain
    SUSTAIN = 3   # Holding at sustain level
    RELEASE = 4   # Falling from sustain to 0
    IDLE = 5      # Silent (not playing)


class Envelope:
    """
    ADSR (Attack, Decay, Sustain, Release) envelope generator.
    
    Controls amplitude modulation of a voice to:
    - Prevent clicks at note start/end
    - Shape the natural timbre
    - Enable dynamic expression
    
    Attributes:
        sample_rate: Audio sample rate in Hz
        attack_time: Time for attack phase in seconds
        decay_time: Time for decay phase in seconds
        sustain_level: Amplitude level during sustain [0, 1]
        release_time: Time for release phase in seconds
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        attack_time: float = 0.01,
        decay_time: float = 0.1,
        sustain_level: float = 0.7,
        release_time: float = 0.3
    ) -> None:
        """
        Initialize ADSR envelope.
        
        Args:
            sample_rate: Audio sample rate in Hz
            attack_time: Attack duration in seconds (default: 10ms)
            decay_time: Decay duration in seconds (default: 100ms)
            sustain_level: Sustain amplitude [0, 1] (default: 0.7)
            release_time: Release duration in seconds (default: 300ms)
        """
        self.sample_rate: int = sample_rate
        
        # Envelope timing parameters (in samples)
        self.attack_samples: int = int(attack_time * sample_rate)
        self.decay_samples: int = int(decay_time * sample_rate)
        self.release_samples: int = int(release_time * sample_rate)
        
        # Ensure minimum 1 sample to prevent division by zero
        self.attack_samples = max(1, self.attack_samples)
        self.decay_samples = max(1, self.decay_samples)
        self.release_samples = max(1, self.release_samples)
        
        # Sustain level
        self.sustain_level: float = np.clip(sustain_level, 0.0, 1.0)
        
        # Envelope state
        self.current_stage: EnvelopeStage = EnvelopeStage.IDLE
        self.sample_counter: int = 0
        self.current_amplitude: float = 0.0
        self.release_start_amplitude: float = 0.0
        self.attack_start_amplitude: float = 0.0

    def trigger(self) -> None:
        """
        Trigger note on (start ATTACK phase).

        Called when a note starts playing. If the voice is retriggered
        while still in release or sustain, we resume the attack from the
        current level instead of resetting to silence.
        """
        self.current_stage = EnvelopeStage.ATTACK
        self.sample_counter = 0
        self.attack_start_amplitude = self.current_amplitude
        self.release_start_amplitude = self.current_amplitude

    def release(self) -> None:
        """
        Trigger note off (start RELEASE phase).

        Called when a note stops playing. Smoothly fades out from the
        current amplitude level.
        """
        if self.current_stage != EnvelopeStage.IDLE:
            self.current_stage = EnvelopeStage.RELEASE
            self.sample_counter = 0
            self.release_start_amplitude = self.current_amplitude
    
    def _update_attack(self) -> float:
        """
        ATTACK phase: ramp from the current level to 1.0.

        This preserves continuity when a note is retriggered quickly before
        the previous envelope has fully faded out.
        """
        start_level = self.attack_start_amplitude
        progress = self.sample_counter / self.attack_samples
        amplitude = start_level + (1.0 - start_level) * progress

        if self.sample_counter >= self.attack_samples - 1:
            self.current_stage = EnvelopeStage.DECAY
            self.sample_counter = 0
            amplitude = 1.0
        else:
            self.sample_counter += 1

        return amplitude
    
    def _update_decay(self) -> float:
        """
        DECAY phase: Ramp from 1.0 to sustain_level
        
        Returns:
            Amplitude value for this sample
        """
        # Linear ramp: 1.0 → sustain_level over decay_samples
        progress = self.sample_counter / self.decay_samples
        amplitude = 1.0 - progress * (1.0 - self.sustain_level)
        
        if self.sample_counter >= self.decay_samples - 1:
            # Decay complete, transition to sustain
            self.current_stage = EnvelopeStage.SUSTAIN
            self.sample_counter = 0
            amplitude = self.sustain_level
        else:
            self.sample_counter += 1
        
        return amplitude
    
    def _update_sustain(self) -> float:
        """
        SUSTAIN phase: Hold at sustain_level
        
        Returns:
            Amplitude value (constant at sustain_level)
        """
        # Sustain stays constant until note off
        return self.sustain_level
    
    def _update_release(self) -> float:
        """
        RELEASE phase: Ramp from current level to 0
        
        Returns:
            Amplitude value for this sample
        """
        # Linear ramp: release_start_amplitude → 0 over release_samples
        progress = self.sample_counter / self.release_samples
        amplitude = self.release_start_amplitude * (1.0 - progress)
        
        if self.sample_counter >= self.release_samples - 1:
            # Release complete, go idle
            self.current_stage = EnvelopeStage.IDLE
            self.sample_counter = 0
            amplitude = 0.0
        else:
            self.sample_counter += 1
        
        return amplitude
    
    def get_next_sample(self) -> float:
        """
        Get the next envelope sample value.
        
        Call this for each audio sample to modulate the oscillator output.
        
        Returns:
            Envelope amplitude for this sample [0, 1]
        """
        if self.current_stage == EnvelopeStage.ATTACK:
            self.current_amplitude = self._update_attack()
        elif self.current_stage == EnvelopeStage.DECAY:
            self.current_amplitude = self._update_decay()
        elif self.current_stage == EnvelopeStage.SUSTAIN:
            self.current_amplitude = self._update_sustain()
        elif self.current_stage == EnvelopeStage.RELEASE:
            self.current_amplitude = self._update_release()
        else:  # IDLE
            self.current_amplitude = 0.0
        
        return self.current_amplitude
    
    def get_next_buffer(self, num_samples: int) -> np.ndarray:
        """
        Get envelope values for an entire buffer of samples.
        
        Efficient vectorized operation for applying envelope to a buffer.
        
        Args:
            num_samples: Number of samples to generate
            
        Returns:
            NumPy array of envelope values [0, 1]
        """
        envelope_values = np.zeros(num_samples, dtype=np.float32)
        
        for i in range(num_samples):
            envelope_values[i] = self.get_next_sample()
        
        return envelope_values
    
    def is_finished(self) -> bool:
        """
        Check if envelope has completed release phase.
        
        Returns:
            True if envelope is idle and can be removed
        """
        return self.current_stage == EnvelopeStage.IDLE
    
    def get_stage_name(self) -> str:
        """
        Get human-readable name of current envelope stage.
        
        Returns:
            Stage name (ATTACK, DECAY, SUSTAIN, RELEASE, or IDLE)
        """
        return self.current_stage.name
    
    def set_parameters(
        self,
        attack_time: Optional[float] = None,
        decay_time: Optional[float] = None,
        sustain_level: Optional[float] = None,
        release_time: Optional[float] = None
    ) -> None:
        """
        Update envelope parameters.
        
        Changes take effect only on next note trigger.
        
        Args:
            attack_time: New attack time in seconds
            decay_time: New decay time in seconds
            sustain_level: New sustain level [0, 1]
            release_time: New release time in seconds
        """
        if attack_time is not None:
            self.attack_samples = max(1, int(attack_time * self.sample_rate))
        
        if decay_time is not None:
            self.decay_samples = max(1, int(decay_time * self.sample_rate))
        
        if sustain_level is not None:
            self.sustain_level = np.clip(sustain_level, 0.0, 1.0)
        
        if release_time is not None:
            self.release_samples = max(1, int(release_time * self.sample_rate))
