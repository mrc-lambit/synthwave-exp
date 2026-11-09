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

from pathlib import Path
from typing import Optional
import wave

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

    # Keep the filter path available while bypassing its per-voice CPU cost.
    FILTER_PROCESSING_ENABLED = False

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
        self.sample: Optional[np.ndarray] = None
        self.sample_path: Optional[str] = None
        self.sample_position: float = 0.0
        self._unison_sample_positions: list[float] = [0.0]
        self.sample_root_frequency: float = 440.0
        self.sample_loop: bool = True  # loop the WAV while the note lasts
        self._sample_ext: Optional[np.ndarray] = None  # sample + first frame (wrap interp)
        
        # Create oscillator for this voice
        self.oscillator: Oscillator = create_oscillator(oscillator_type, sample_rate)
        self.unison_oscillators: list[Oscillator] = [self.oscillator]
        self.unison_voices: int = 1
        self.detune_cents: float = 0.0
        self.synthesis_mode: str = 'waveform'
        self.additive_partials: int = 8
        self.additive_tilt_db_per_octave: float = 6.0
        self.fm_ratio: float = 2.0
        self.fm_index: float = 2.0
        self._additive_phases = np.zeros((7, 16), dtype=np.float64)
        self._fm_carrier_phases = np.zeros(7, dtype=np.float64)
        self._fm_modulator_phases = np.zeros(7, dtype=np.float64)
        
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
        self._filter_params = ('lowpass', 2000.0, 0.0)
        
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
        self.sample_position = 0.0
        self._unison_sample_positions = [0.0] * self.unison_voices
        
        # Reset phase only for a silent voice: on a retriggered/stolen voice
        # that is still sounding, a phase jump would be heard as a click.
        if self.envelope.is_finished():
            for oscillator in self.unison_oscillators:
                oscillator.reset_phase()
            self._additive_phases.fill(0.0)
            self._fm_carrier_phases.fill(0.0)
            self._fm_modulator_phases.fill(0.0)
        
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
        if oscillator_type == self.oscillator_type:
            return  # keep oscillator (and its phase) untouched
        self.oscillator_type = oscillator_type
        self.unison_oscillators = [
            create_oscillator(oscillator_type, self.sample_rate)
            for _ in range(self.unison_voices)
        ]
        self.oscillator = self.unison_oscillators[0]

    def set_unison_parameters(self, voices: int = 1, detune_cents: float = 0.0) -> None:
        """Set the number of stacked oscillators and their maximum pitch spread."""
        voices = int(np.clip(voices, 1, 7))
        detune_cents = float(np.clip(detune_cents, 0.0, 50.0))
        current_voices = len(self.unison_oscillators)
        if voices < current_voices:
            self.unison_oscillators = self.unison_oscillators[:voices]
            self._unison_sample_positions = self._unison_sample_positions[:voices]
        elif voices > current_voices:
            for _ in range(voices - current_voices):
                oscillator = create_oscillator(self.oscillator_type, self.sample_rate)
                oscillator.phase = self.oscillator.phase
                self.unison_oscillators.append(oscillator)
            self._unison_sample_positions.extend(
                [self.sample_position] * (voices - current_voices)
            )
        self.unison_voices = voices
        self.detune_cents = detune_cents
        self.oscillator = self.unison_oscillators[0]

    def set_synthesis_mode(self, mode: str) -> None:
        """Select waveform, additive, or frequency-modulation synthesis."""
        mode = mode.lower()
        if mode not in {'waveform', 'additive', 'fm'}:
            raise ValueError(f"Unknown synthesis mode: {mode}")
        self.synthesis_mode = mode

    def set_synthesis_parameters(
        self,
        additive_partials: int = 8,
        additive_tilt_db_per_octave: float = 6.0,
        fm_ratio: float = 2.0,
        fm_index: float = 2.0,
    ) -> None:
        """Update additive spectrum and FM operator settings."""
        self.additive_partials = int(np.clip(additive_partials, 1, 16))
        self.additive_tilt_db_per_octave = float(
            np.clip(additive_tilt_db_per_octave, 0.0, 24.0)
        )
        self.fm_ratio = float(np.clip(fm_ratio, 0.5, 8.0))
        self.fm_index = float(np.clip(fm_index, 0.0, 12.0))

    def _phase_sequence(
        self, phase: float, frequency: np.ndarray, num_samples: int
    ) -> tuple[np.ndarray, float]:
        increments = np.asarray(frequency, dtype=np.float64) / self.sample_rate
        if increments.ndim == 0:
            increments = np.full(num_samples, increments, dtype=np.float64)
        phases = phase + np.concatenate((
            np.zeros(1, dtype=np.float64),
            np.cumsum(increments[:-1]),
        ))
        next_phase = float((phase + np.sum(increments)) % 1.0)
        return np.remainder(phases, 1.0), next_phase

    def _generate_additive(
        self, frequency: np.ndarray, amplitude: float, num_samples: int,
        detune_ratio: float, unison_index: int,
    ) -> np.ndarray:
        output = np.zeros(num_samples, dtype=np.float64)
        partial_numbers = np.arange(1, self.additive_partials + 1)
        weights = np.power(
            10.0,
            -self.additive_tilt_db_per_octave
            * np.log2(partial_numbers)
            / 20.0,
        )
        weight_sum = float(np.sum(weights))
        base_frequency = np.asarray(frequency, dtype=np.float64) * detune_ratio
        nyquist = self.sample_rate / 2.0

        for partial_index, (partial, weight) in enumerate(
            zip(partial_numbers, weights)
        ):
            partial_frequency = base_frequency * partial
            phases, next_phase = self._phase_sequence(
                self._additive_phases[unison_index, partial_index],
                partial_frequency,
                num_samples,
            )
            self._additive_phases[unison_index, partial_index] = next_phase
            audible = partial_frequency < nyquist
            output += np.sin(2.0 * np.pi * phases) * audible * weight

        return (output * (amplitude / (self.unison_voices * weight_sum))).astype(
            np.float32
        )

    def _generate_fm(
        self, frequency: np.ndarray, amplitude: float, num_samples: int,
        detune_ratio: float, unison_index: int,
    ) -> np.ndarray:
        nyquist_limit = self.sample_rate * 0.45
        carrier_frequency = np.clip(
            np.asarray(frequency, dtype=np.float64) * detune_ratio,
            0.0,
            nyquist_limit,
        )
        modulator_frequency = np.clip(
            carrier_frequency * self.fm_ratio,
            0.0,
            nyquist_limit,
        )
        carrier_phases, self._fm_carrier_phases[unison_index] = (
            self._phase_sequence(
                self._fm_carrier_phases[unison_index],
                carrier_frequency,
                num_samples,
            )
        )
        modulator_phases, self._fm_modulator_phases[unison_index] = (
            self._phase_sequence(
                self._fm_modulator_phases[unison_index],
                modulator_frequency,
                num_samples,
            )
        )
        phase = carrier_phases + self.fm_index * np.sin(
            2.0 * np.pi * modulator_phases
        )
        return (
            np.sin(2.0 * np.pi * phase)
            * amplitude
            / self.unison_voices
        ).astype(np.float32)

    def load_sample(self, path: str, root_frequency: float = 440.0) -> None:
        """Load and normalize a PCM WAV sample for chromatic playback."""
        sample_path = Path(path)
        with wave.open(str(sample_path), 'rb') as wav_file:
            channels = wav_file.getnchannels()
            width = wav_file.getsampwidth()
            source_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            raw = wav_file.readframes(frames)

        if width == 1:
            audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif width == 2:
            audio = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
        elif width == 3:
            values = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            integers = (values[:, 0].astype(np.int32)
                        | (values[:, 1].astype(np.int32) << 8)
                        | (values[:, 2].astype(np.int32) << 16))
            integers = np.where(integers & 0x800000, integers - 0x1000000, integers)
            audio = integers.astype(np.float32) / 8388608.0
        elif width == 4:
            audio = np.frombuffer(raw, dtype='<i4').astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {width} bytes")

        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        if audio.size == 0:
            raise ValueError("The selected WAV file contains no audio")
        if source_rate != self.sample_rate:
            output_size = max(1, int(round(audio.size * self.sample_rate / source_rate)))
            audio = np.interp(
                np.arange(output_size) * (source_rate / self.sample_rate),
                np.arange(audio.size),
                audio,
            )

        self.sample = audio.astype(np.float32)
        self._sample_ext = np.append(self.sample, self.sample[0])
        self.sample_path = str(sample_path.resolve())
        self.sample_root_frequency = max(1.0, float(root_frequency))
        self.sample_position = 0.0
        self._unison_sample_positions = [0.0] * self.unison_voices

    def clear_sample(self) -> None:
        """Unload the current sample."""
        self.sample = None
        self._sample_ext = None
        self.sample_path = None
        self.sample_position = 0.0
        self._unison_sample_positions = [0.0] * self.unison_voices

    def set_sample_loop(self, enabled: bool) -> None:
        """Enable/disable looping of the sample for the duration of the note."""
        self.sample_loop = bool(enabled)

    def set_sample_root_frequency(self, frequency: float) -> None:
        self.sample_root_frequency = max(1.0, float(frequency))
        
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
        params = (kind, float(cutoff), float(resonance))
        if params == self._filter_params:
            # Unchanged: keep filter state, only undo any LFO cutoff modulation
            if self.filter.cutoff != self.base_filter_cutoff:
                self.filter.cutoff = self.base_filter_cutoff
            return
        self._filter_params = params
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
        
        effective_frequency = self.frequency
        effective_amplitude = self.amplitude

        if (
            self.lfo.frequency > 0.0
            and self.lfo.depth > 0.0
            and (self.lfo_target != 'filter' or self.FILTER_PROCESSING_ENABLED)
        ):
            modulation = self.lfo.generate(num_samples)
            if np.any(modulation != 0.0):
                if self.lfo_target == 'pitch':
                    effective_frequency = self.frequency * (1.0 + modulation)
                elif self.lfo_target == 'volume':
                    effective_amplitude = np.clip(
                        self.amplitude * (1.0 + modulation), 0.0, 1.0
                    )
                elif self.lfo_target == 'filter':
                    block_modulation = float(np.mean(modulation))
                    self.filter.cutoff = max(
                        20.0, self.base_filter_cutoff * (1.0 + block_modulation)
                    )

        if self.sample is not None:
            pitch_ratio = np.asarray(effective_frequency, dtype=np.float64) / self.sample_root_frequency
            if pitch_ratio.ndim == 0:
                pitch_ratio = np.full(num_samples, pitch_ratio, dtype=np.float64)
            offsets = (
                np.linspace(-1.0, 1.0, self.unison_voices, dtype=np.float32)
                if self.unison_voices > 1
                else np.zeros(1, dtype=np.float32)
            )
            samples = np.zeros(num_samples, dtype=np.float32)
            for index, offset in enumerate(offsets):
                detune_ratio = 2.0 ** (
                    float(offset) * self.detune_cents / 1200.0
                )
                voice_pitch_ratio = pitch_ratio * detune_ratio
                positions = self._unison_sample_positions[index] + np.concatenate((
                    np.zeros(1, dtype=np.float64),
                    np.cumsum(voice_pitch_ratio[:-1]),
                ))
                if self.sample_loop and self._sample_ext is not None:
                    length = len(self.sample)
                    wrapped_positions = positions % length
                    sample_indices = wrapped_positions.astype(np.int64)
                    frac = (wrapped_positions - sample_indices).astype(np.float32)
                    ext = self._sample_ext
                    voice_samples = (
                        ext[sample_indices] * (1.0 - frac)
                        + ext[sample_indices + 1] * frac
                    )
                    self._unison_sample_positions[index] = (
                        self._unison_sample_positions[index]
                        + float(np.sum(voice_pitch_ratio))
                    ) % length
                else:
                    valid = positions < len(self.sample)
                    voice_samples = np.zeros(num_samples, dtype=np.float32)
                    if np.any(valid):
                        voice_samples[valid] = np.interp(
                            positions[valid],
                            np.arange(len(self.sample)),
                            self.sample,
                        ).astype(np.float32)
                    self._unison_sample_positions[index] += float(
                        np.sum(voice_pitch_ratio)
                    )
                samples += voice_samples / self.unison_voices
            self.sample_position = self._unison_sample_positions[0]
            samples *= effective_amplitude
        else:
            offsets = np.linspace(
                -1.0, 1.0, self.unison_voices, dtype=np.float32
            )
            if self.unison_voices == 1:
                offsets[0] = 0.0
            samples = np.zeros(num_samples, dtype=np.float32)
            for index, (oscillator, offset) in enumerate(
                zip(self.unison_oscillators, offsets)
            ):
                detune_ratio = 2.0 ** (
                    float(offset) * self.detune_cents / 1200.0
                )
                if self.synthesis_mode == 'additive':
                    samples += self._generate_additive(
                        effective_frequency,
                        effective_amplitude,
                        num_samples,
                        detune_ratio,
                        index,
                    )
                elif self.synthesis_mode == 'fm':
                    samples += self._generate_fm(
                        effective_frequency,
                        effective_amplitude,
                        num_samples,
                        detune_ratio,
                        index,
                    )
                else:
                    samples += oscillator.generate(
                        frequency=effective_frequency * detune_ratio,
                        num_samples=num_samples,
                        amplitude=effective_amplitude / self.unison_voices,
                    )
        
        # Get envelope values for this buffer
        envelope_values = self.envelope.get_next_buffer(num_samples)
        
        # Apply envelope to oscillator output
        samples = samples * envelope_values

        if self.FILTER_PROCESSING_ENABLED:
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
