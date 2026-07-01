# -*- coding: utf-8 -*-
"""
Voice module for the MUSA software synthesizer.

A Voice represents a single active note/sound in the synthesizer.
Multiple voices are combined in the Mixer to achieve polyphony.

Each voice maintains:
- Oscillator state and waveform selection
- Frequency and amplitude
- ADSR envelope state
- Active/inactive status
"""

from typing import Optional

import numpy as np

from audio.oscillator import Oscillator, create_oscillator
from audio.envelope import Envelope
from audio.filter import Filter
from audio.lfo import LFO


class Voice:
    """
    Represents a single active voice (note) in the synthesizer.
    
    A voice is responsible for:
    - Generating audio samples at a specific frequency
    - Managing its active state (note on/off)
    - Applying amplitude and ADSR envelope
    - Interfacing with oscillator and envelope
    
    Multiple voices are combined by the Mixer for polyphony.
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        oscillator_type: str = 'sine'
    ) -> None:
        """
        Initialize a voice with a specific oscillator type.
        
        Args:
            sample_rate: Audio sample rate in Hz (default: 44100)
            oscillator_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        self.sample_rate: int = sample_rate
        self.oscillator_type: str = oscillator_type
        
        # Create oscillator for this voice
        self.oscillator: Oscillator = create_oscillator(oscillator_type, sample_rate)
        
        # Create ADSR envelope
        self.envelope: Envelope = Envelope(
            sample_rate=sample_rate,
            attack_time=0.01,      # 10ms attack
            decay_time=0.1,        # 100ms decay
            sustain_level=0.7,     # 70% sustain
            release_time=0.3       # 300ms release
        )

        self.filter: Filter = Filter(kind='lowpass', cutoff=2000.0, resonance=0.0)
        self.lfo: LFO = LFO(sample_rate=sample_rate, frequency=0.0, depth=0.0)
        self.lfo_target: str = 'pitch'
        self.base_filter_cutoff: float = 2000.0
        
        # Voice state
        self.is_active: bool = False
        self.frequency: float = 0.0  # Hz
        self.amplitude: float = 0.5  # [0, 1]
        
    def note_on(self, frequency: float, amplitude: float = 0.5) -> None:
        """
        Trigger a note on event.
        
        Called when a note starts playing. Resets oscillator phase
        and starts envelope attack phase.
        
        Args:
            frequency: Note frequency in Hz (e.g., 440.0 for A4)
            amplitude: Initial amplitude [0, 1]
        """
        self.frequency = frequency
        self.amplitude = amplitude
        self.is_active = True
        
        # Reset oscillator phase for seamless note start
        self.oscillator.reset_phase()
        
        # Trigger envelope attack
        self.envelope.trigger()
        
    def note_off(self) -> None:
        """
        Trigger a note off event.
        
        Called when a note stops. Initiates envelope release phase.
        The voice remains active until release completes and envelope
        reaches zero.
        """
        self.is_active = False
        
        # Trigger envelope release
        self.envelope.release()
        
    def set_waveform(self, oscillator_type: str) -> None:
        """
        Change the waveform type for this voice.
        
        Args:
            oscillator_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        self.oscillator_type = oscillator_type
        self.oscillator = create_oscillator(oscillator_type, self.sample_rate)
        
    def set_frequency(self, frequency: float) -> None:
        """
        Update the frequency of this voice.
        
        Useful for parameter modulation (pitch bending, vibrato, etc.).
        
        Args:
            frequency: New frequency in Hz
        """
        self.frequency = frequency
        
    def set_amplitude(self, amplitude: float) -> None:
        """
        Update the amplitude of this voice.
        
        Useful for volume modulation (tremolo, etc.).
        
        Args:
            amplitude: New amplitude [0, 1]
        """
        self.amplitude = np.clip(amplitude, 0.0, 1.0)
    
    def set_envelope_parameters(
        self,
        attack_time: float = 0.01,
        decay_time: float = 0.1,
        sustain_level: float = 0.7,
        release_time: float = 0.3
    ) -> None:
        """
        Update ADSR envelope parameters.
        
        Args:
            attack_time: Attack duration in seconds
            decay_time: Decay duration in seconds
            sustain_level: Sustain level [0, 1]
            release_time: Release duration in seconds
        """
        self.envelope.set_parameters(
            attack_time=attack_time,
            decay_time=decay_time,
            sustain_level=sustain_level,
            release_time=release_time
        )
        
    def set_filter(self, kind: str, cutoff: float, resonance: float) -> None:
        """Update the voice filter settings."""
        self.filter = Filter(kind=kind, cutoff=cutoff, resonance=resonance)
        self.base_filter_cutoff = float(cutoff)

    def set_lfo_parameters(self, frequency: float = 0.0, depth: float = 0.0, target: str = 'pitch') -> None:
        """Configure the LFO used for modulation."""
        self.lfo.set_parameters(frequency=frequency, depth=depth)
        self.lfo_target = target.lower()

    def generate(self, num_samples: int) -> np.ndarray:
        """
        Generate audio samples for this voice.
        
        This is called by the Mixer for each buffer. If the voice is inactive
        and envelope is finished, returns silence. If active or envelope is
        still releasing, generates samples from the oscillator and applies
        amplitude and envelope.
        
        Args:
            num_samples: Number of samples to generate
            
        Returns:
            NumPy array of audio samples (float32)
        """
        # Check if voice is completely finished
        if not self.is_active and self.envelope.is_finished():
            return np.zeros(num_samples, dtype=np.float32)
        
        modulation = self.lfo.generate(num_samples)
        effective_frequency = self.frequency
        effective_amplitude = self.amplitude

        if self.lfo_target == 'pitch' and np.any(modulation != 0.0):
            effective_frequency = self.frequency * (1.0 + modulation)
        elif self.lfo_target == 'volume' and np.any(modulation != 0.0):
            effective_amplitude = np.clip(self.amplitude * (1.0 + modulation), 0.0, 1.0)
        elif self.lfo_target == 'filter' and np.any(modulation != 0.0):
            self.filter.cutoff = max(20.0, self.base_filter_cutoff * (1.0 + modulation))

        # Generate samples from oscillator at current frequency
        samples = self.oscillator.generate(
            frequency=effective_frequency,
            num_samples=num_samples,
            amplitude=effective_amplitude
        )
        
        # Get envelope values for this buffer
        envelope_values = self.envelope.get_next_buffer(num_samples)
        
        # Apply envelope to oscillator output
        samples = samples * envelope_values

        # Apply filter
        samples = self.filter.process(samples, self.sample_rate)
        
        return samples.astype(np.float32)
    
    def is_ready_to_remove(self) -> bool:
        """
        Check if voice can be safely removed from the mixer.
        
        A voice can be removed when it's inactive AND its envelope
        has fully decayed to silence (after release phase).
        
        This prevents notes from being cut off abruptly.
        
        Returns:
            True if voice is done and can be removed, False otherwise
        """
        return not self.is_active and self.envelope.is_finished()
