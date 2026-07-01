# -*- coding: utf-8 -*-
"""
Mixer module for the MUSA software synthesizer.

The Mixer combines multiple voices to achieve polyphony.
It manages a pool of available voices and mixing/summing their outputs.

Key responsibilities:
- Manage voice allocation (note_on requests → available Voice)
- Mix audio from all active voices
- Handle voice cleanup when notes end
- Apply master volume and soft clipping
"""

from typing import Dict, List, Optional

import numpy as np

from audio.voice import Voice


class Mixer:
    """
    Polyphonic mixer that combines multiple Voice outputs.
    
    Manages a pool of voices and mixes their outputs into a stereo buffer.
    Handles voice allocation, cleanup, and amplitude normalization.
    
    Attributes:
        max_voices: Maximum number of simultaneous voices
        sample_rate: Audio sample rate in Hz
        master_volume: Master output volume [0, 1]
    """
    
    def __init__(
        self,
        max_voices: int = 32,
        sample_rate: int = 44100
    ) -> None:
        """
        Initialize the mixer with a pool of voices.
        
        Args:
            max_voices: Maximum simultaneous voices (default: 32)
            sample_rate: Audio sample rate in Hz (default: 44100)
        """
        self.max_voices: int = max_voices
        self.sample_rate: int = sample_rate
        
        # Voice pool: available and active voices
        self.voices: List[Voice] = [
            Voice(sample_rate=sample_rate, oscillator_type='sine')
            for _ in range(max_voices)
        ]
        self.active_voices: List[Voice] = []
        
        # Master control
        self.master_volume: float = 0.8  # [0, 1]
        
        # Clipping prevention (soft clipping threshold)
        self.soft_clip_threshold: float = 0.95
        
    def note_on(
        self,
        frequency: float,
        amplitude: float = 0.5,
        oscillator_type: str = 'sine'
    ) -> Optional[Voice]:
        """
        Request a new voice for a note.
        
        Allocates an available voice from the pool, starts the note,
        and adds it to the active voices list.
        
        Args:
            frequency: Note frequency in Hz
            amplitude: Note amplitude [0, 1]
            oscillator_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
            
        Returns:
            Voice instance if allocated, None if no voices available
        """
        if len(self.active_voices) >= self.max_voices:
            # No voices available - steal oldest voice
            stolen_voice = self.active_voices.pop(0)
            self.active_voices.append(stolen_voice)
        else:
            # Find an inactive voice
            for voice in self.voices:
                if voice not in self.active_voices:
                    self.active_voices.append(voice)
                    break
        
        # Get the voice to use
        voice = self.active_voices[-1]
        
        # Configure and start the voice
        voice.set_waveform(oscillator_type)
        voice.note_on(frequency=frequency, amplitude=amplitude)
        
        return voice
    
    def note_off(self, voice: Voice) -> None:
        """
        Stop a voice.
        
        Args:
            voice: Voice instance to stop
        """
        if voice in self.active_voices:
            voice.note_off()
    
    def set_oscillator_type(self, oscillator_type: str) -> None:
        """
        Set the oscillator type for ALL active voices.
        
        Useful for changing the sound globally.
        
        Args:
            oscillator_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        for voice in self.active_voices:
            voice.set_waveform(oscillator_type)

    def set_adsr_parameters(
        self,
        attack_time: float = 0.01,
        decay_time: float = 0.1,
        sustain_level: float = 0.7,
        release_time: float = 0.3,
    ) -> None:
        """Update ADSR parameters for all active voices."""
        for voice in self.active_voices:
            voice.set_envelope_parameters(
                attack_time=attack_time,
                decay_time=decay_time,
                sustain_level=sustain_level,
                release_time=release_time,
            )
    
    def set_filter(self, kind: str, cutoff: float, resonance: float) -> None:
        """Update the filter settings for all active voices."""
        for voice in self.active_voices:
            voice.set_filter(kind=kind, cutoff=cutoff, resonance=resonance)

    def set_lfo_parameters(self, frequency: float = 0.0, depth: float = 0.0, target: str = 'pitch') -> None:
        """Update LFO modulation settings for all active voices."""
        for voice in self.active_voices:
            voice.set_lfo_parameters(frequency=frequency, depth=depth, target=target)

    def set_master_volume(self, volume: float) -> None:
        """
        Set the master output volume.
        
        Args:
            volume: Volume level [0, 1]
        """
        self.master_volume = np.clip(volume, 0.0, 1.0)
    
    def _cleanup_finished_voices(self) -> None:
        """
        Remove voices that have finished playing (envelope release complete).
        
        This makes voices available for new note_on requests.
        """
        self.active_voices = [
            voice for voice in self.active_voices
            if not voice.is_ready_to_remove()
        ]
    
    def _soft_clip(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply soft clipping to prevent harsh distortion.
        
        Soft clipping uses a smooth sigmoid-like curve to limit peaks
        without the harsh aliasing of hard clipping.
        
        Formula: y = tanh(x) for soft saturation effect
        
        Args:
            samples: Audio samples to clip
            
        Returns:
            Clipped audio samples
        """
        # Simple soft clipping using tanh
        # tanh smoothly compresses samples above threshold
        return np.tanh(samples)
    
    def mix(self, num_samples: int) -> np.ndarray:
        """
        Generate mixed audio buffer from all active voices.
        
        This is the main audio generation function. It:
        1. Generates samples from each active voice
        2. Sums all voices together
        3. Applies master volume
        4. Applies soft clipping to prevent distortion
        5. Cleans up finished voices
        
        Args:
            num_samples: Number of samples to generate
            
        Returns:
            NumPy array of mixed mono audio samples (float32)
        """
        # Initialize output buffer with zeros
        output = np.zeros(num_samples, dtype=np.float32)
        
        # Sum all active voice outputs
        for voice in self.active_voices:
            voice_samples = voice.generate(num_samples)
            output += voice_samples
        
        # Normalize by number of active voices to prevent excessive volume
        if len(self.active_voices) > 0:
            output = output / (len(self.active_voices) ** 0.5)
        
        # Apply master volume
        output = output * self.master_volume
        
        # Apply soft clipping to prevent distortion
        output = self._soft_clip(output)
        
        # Remove finished voices for future allocation
        self._cleanup_finished_voices()
        
        return output.astype(np.float32)
    
    def get_active_voice_count(self) -> int:
        """
        Get the current number of active voices.
        
        Returns:
            Number of voices currently playing
        """
        return len(self.active_voices)
    
    def stop_all(self) -> None:
        """
        Stop all active voices immediately.
        
        Useful for silence/panic button.
        """
        for voice in self.active_voices:
            voice.note_off()
        self.active_voices.clear()
    
    def get_cpu_load(self) -> float:
        """
        Estimate CPU load as percentage of voices in use.
        
        Returns:
            CPU load estimate [0, 1] where 1.0 = all voices in use
        """
        return len(self.active_voices) / self.max_voices
