# -*- coding: utf-8 -*-
"""
Oscillator module for the MUSA software synthesizer.

Implements multiple waveform types for DSP-based audio synthesis:
- Sine wave
- Square wave
- Triangle wave
- Sawtooth wave

All oscillators generate mathematically computed samples in real-time
without using pre-recorded samples.

Mathematical foundations:
- All waveforms are created using phase accumulation
- Phase is stored as floating-point value [0, 1) representing [0, 2π)
- Efficient computation using NumPy vectorization
"""

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class Oscillator(ABC):
    """
    Abstract base class for all oscillator types.
    
    Defines the interface and common functionality for generating audio waveforms.
    Subclasses must implement the generate() method with specific waveform generation logic.
    """
    
    def __init__(self, sample_rate: int = 44100) -> None:
        """
        Initialize the oscillator.
        
        Args:
            sample_rate: Audio sample rate in Hz (default: 44100 Hz for CD quality)
        """
        self.sample_rate: int = sample_rate
        self.phase: float = 0.0  # Phase accumulator [0, 1)
        
    @abstractmethod
    def generate(
        self,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0
    ) -> np.ndarray:
        """
        Generate audio samples for the waveform.
        
        Args:
            frequency: Oscillator frequency in Hz
            num_samples: Number of samples to generate
            amplitude: Waveform amplitude [0, 1]
            
        Returns:
            NumPy array of audio samples (float32), range [-amplitude, +amplitude]
        """
        pass
    
    def _phase_increment(self, frequency: float) -> float:
        """
        Calculate phase increment per sample.
        
        This is the amount by which the phase accumulator should advance
        for each sample at the given frequency.
        
        Formula: phase_inc = frequency / sample_rate
        
        Args:
            frequency: Frequency in Hz
            
        Returns:
            Phase increment per sample (normalized to [0, 1))
        """
        return frequency / self.sample_rate
    
    def _update_phase(self, phase_increment: float, num_samples: int) -> np.ndarray:
        """
        Generate phase values for a buffer of samples.
        
        Uses phase accumulation with wraparound at 1.0 to maintain
        continuous phase continuity across buffer boundaries.
        
        Args:
            phase_increment: Amount to increment phase per sample
            num_samples: Number of phase values to generate
            
        Returns:
            NumPy array of phase values [0, 1)
        """
        # Create phase values for all samples in this buffer
        phase_values = np.arange(num_samples, dtype=np.float32) * phase_increment
        phase_values += self.phase
        
        # Wrap phase to [0, 1)
        phase_values = np.fmod(phase_values, 1.0)
        
        # Update stored phase for continuity in next buffer
        self.phase = phase_values[-1] + phase_increment
        self.phase = np.fmod(self.phase, 1.0)
        
        return phase_values
    
    def reset_phase(self) -> None:
        """Reset the phase accumulator to 0. Useful for note/voice resets."""
        self.phase = 0.0


class SineOscillator(Oscillator):
    """
    Sine wave oscillator.
    
    Generates smooth, pure sine waveforms.
    Formula: y = sin(2π * phase)
    
    Characteristics:
    - Smooth, pure tone
    - No harmonics (ideal fundamental)
    - Most natural sounding
    """
    
    def generate(
        self,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0
    ) -> np.ndarray:
        """
        Generate sine wave samples.
        
        Args:
            frequency: Oscillator frequency in Hz
            num_samples: Number of samples to generate
            amplitude: Waveform amplitude [0, 1]
            
        Returns:
            NumPy array of sine wave samples
        """
        phase_inc = self._phase_increment(frequency)
        phases = self._update_phase(phase_inc, num_samples)
        
        # Convert phase [0, 1) to radians [0, 2π)
        # sin(2π * phase) generates pure sine wave
        samples = amplitude * np.sin(2.0 * np.pi * phases)
        
        return samples.astype(np.float32)


class SquareOscillator(Oscillator):
    """
    Square wave oscillator.
    
    Generates square (pulse) waveforms with 50% duty cycle.
    Formula: y = +1 if phase < 0.5, else -1
    
    Characteristics:
    - Bright, harsh tone
    - Contains odd harmonics (1f, 3f, 5f, 7f, ...)
    - Rich harmonic content
    - Classic digital synth sound
    """
    
    def generate(
        self,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0
    ) -> np.ndarray:
        """
        Generate square wave samples.
        
        Args:
            frequency: Oscillator frequency in Hz
            num_samples: Number of samples to generate
            amplitude: Waveform amplitude [0, 1]
            
        Returns:
            NumPy array of square wave samples
        """
        phase_inc = self._phase_increment(frequency)
        phases = self._update_phase(phase_inc, num_samples)
        
        # Square wave: +1 when phase < 0.5, -1 otherwise
        samples = np.where(phases < 0.5, 1.0, -1.0)
        samples = amplitude * samples
        
        return samples.astype(np.float32)


class TriangleOscillator(Oscillator):
    """
    Triangle wave oscillator.
    
    Generates triangle waveforms with linear ramps.
    Formula: 
        - Ascending phase [0, 0.5): y = 4 * phase - 1
        - Descending phase [0.5, 1): y = 3 - 4 * phase
    
    Characteristics:
    - Smooth, mellow tone
    - Contains odd harmonics with less intensity than square
    - Warmer than square, brighter than sine
    - Good for softer synth tones
    """
    
    def generate(
        self,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0
    ) -> np.ndarray:
        """
        Generate triangle wave samples.
        
        Args:
            frequency: Oscillator frequency in Hz
            num_samples: Number of samples to generate
            amplitude: Waveform amplitude [0, 1]
            
        Returns:
            NumPy array of triangle wave samples
        """
        phase_inc = self._phase_increment(frequency)
        phases = self._update_phase(phase_inc, num_samples)
        
        # Triangle wave construction:
        # For first half of cycle (0 to 0.5): ramp from -1 to +1
        # For second half (0.5 to 1): ramp from +1 to -1
        samples = np.where(
            phases < 0.5,
            4.0 * phases - 1.0,      # Ascending: -1 to +1
            3.0 - 4.0 * phases       # Descending: +1 to -1
        )
        samples = amplitude * samples
        
        return samples.astype(np.float32)


class SawtoothOscillator(Oscillator):
    """
    Sawtooth wave oscillator.
    
    Generates sawtooth (ramp) waveforms with sharp discontinuity.
    Formula: y = 2 * phase - 1
    
    Characteristics:
    - Bright, buzzy, edgy tone
    - Contains all harmonics (1f, 2f, 3f, 4f, ...)
    - Rich harmonic content
    - Most harmonically dense of the basic waveforms
    - Classic subtractive synthesis starting point
    """
    
    def generate(
        self,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0
    ) -> np.ndarray:
        """
        Generate sawtooth wave samples.
        
        Args:
            frequency: Oscillator frequency in Hz
            num_samples: Number of samples to generate
            amplitude: Waveform amplitude [0, 1]
            
        Returns:
            NumPy array of sawtooth wave samples
        """
        phase_inc = self._phase_increment(frequency)
        phases = self._update_phase(phase_inc, num_samples)
        
        # Sawtooth wave: linear ramp from -1 to +1
        # Formula: y = 2 * phase - 1
        samples = 2.0 * phases - 1.0
        samples = amplitude * samples
        
        return samples.astype(np.float32)


# Factory function for creating oscillators by type
def create_oscillator(osc_type: str, sample_rate: int = 44100) -> Oscillator:
    """
    Factory function to create oscillators by type name.
    
    Args:
        osc_type: Oscillator type ('sine', 'square', 'triangle', 'sawtooth')
        sample_rate: Audio sample rate in Hz
        
    Returns:
        Oscillator instance of the requested type
        
    Raises:
        ValueError: If osc_type is not recognized
    """
    oscillators = {
        'sine': SineOscillator,
        'square': SquareOscillator,
        'triangle': TriangleOscillator,
        'sawtooth': SawtoothOscillator,
    }
    
    if osc_type.lower() not in oscillators:
        raise ValueError(
            f"Unknown oscillator type: {osc_type}. "
            f"Supported types: {', '.join(oscillators.keys())}"
        )
    
    return oscillators[osc_type.lower()](sample_rate)
