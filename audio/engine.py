# -*- coding: utf-8 -*-
"""
Audio Engine module for the MUSA software synthesizer.

The AudioEngine handles real-time audio I/O using sounddevice.
It manages a separate thread for audio processing to minimize latency
and prevent blocking of the GUI thread.

Key features:
- Real-time audio streaming at 44.1 kHz
- Configurable buffer size (256-512 samples)
- Separate audio thread for stable I/O
- Thread-safe communication with GUI
"""

from threading import Thread, Event, Lock
from typing import Callable, Optional, Any
from pathlib import Path

import numpy as np
import sounddevice as sd
import wave

from audio.mixer import Mixer


class AudioEngine:
    """
    Real-time audio streaming engine using sounddevice.
    
    Manages audio device I/O, buffer handling, and the audio processing thread.
    Communicates with the mixer to generate samples in real-time.
    
    Attributes:
        sample_rate: Audio sample rate in Hz (44100)
        buffer_size: Number of samples per buffer (256-512)
        mixer: Mixer instance for voice management
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        buffer_size: int = 1024,
        max_voices: int = 32
    ) -> None:
        """
        Initialize the audio engine.
        
        Args:
            sample_rate: Audio sample rate in Hz (default: 44100)
            buffer_size: Samples per buffer (default: 256 = ~12ms latency)
            max_voices: Maximum simultaneous voices (default: 32)
        """
        self.sample_rate: int = sample_rate
        self.buffer_size: int = max(512, int(buffer_size))
        self.max_voices: int = max_voices
        
        # Create mixer for voice management
        self.mixer: Mixer = Mixer(
            max_voices=max_voices,
            sample_rate=sample_rate
        )
        
        # Audio stream state
        self.stream: Optional[sd.OutputStream] = None
        self.is_running: bool = False
        
        # Thread management
        self.audio_thread: Optional[Thread] = None
        self.stop_event: Event = Event()
        
        # Circular buffer for waveform capture (for oscilloscope)
        self.waveform_buffer: np.ndarray = np.zeros(
            2048, dtype=np.float32
        )  # ~46ms at 44.1kHz
        self.waveform_index: int = 0
        self.waveform_lock: Lock = Lock()
        
        # Performance metrics
        self.sample_count: int = 0
        self.underrun_count: int = 0
        self.recording_path: Optional[Path] = None
        self.recording_file: Optional[wave.Wave_write] = None
        
    def start(self) -> None:
        """
        Start the audio engine and streaming thread.
        
        Initializes the audio device and begins real-time audio streaming.
        """
        if self.is_running:
            return
        
        try:
            # Create audio output stream
            # Using callback mode for real-time processing
            self.stream = sd.OutputStream(
                channels=1,  # Mono output
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                callback=self._audio_callback,
                latency='high'  # Use a safer latency budget to avoid underruns
            )
            
            # Start the stream
            self.stream.start()
            self.is_running = True
            self.stop_event.clear()
            
            print(f"[AudioEngine] Started - "
                  f"SR: {self.sample_rate}Hz, "
                  f"Buffer: {self.buffer_size} samples, "
                  f"Latency: ~{self.buffer_size * 1000 / self.sample_rate:.1f}ms")
            
        except Exception as e:
            print(f"[AudioEngine] ERROR starting stream: {e}")
            self.is_running = False
            stream = self.stream
            self.stream = None
            if stream is not None:
                try:
                    stream.close()
                except Exception as close_error:
                    print(f"[AudioEngine] ERROR closing failed stream: {close_error}")
    
    def stop(self) -> None:
        """
        Stop the audio engine and stream.
        
        Safely closes the audio stream and stops processing.
        """
        if not self.is_running and self.stream is None:
            self.stop_recording()
            return
        
        self.is_running = False
        self.stop_event.set()
        
        stream = self.stream
        self.stream = None
        try:
            if stream:
                try:
                    stream.stop()
                finally:
                    stream.close()
        finally:
            self.mixer.stop_all()
            self.stop_recording()
        
        print("[AudioEngine] Stopped")
    
    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any
    ) -> None:
        """
        Callback function for real-time audio generation.
        
        Called by sounddevice when audio buffer needs to be filled.
        This runs in a high-priority audio thread.
        
        Args:
            outdata: Output buffer to fill with audio samples
            frames: Number of samples required
            time_info: Timestamp info (unused here)
            status: Flags indicating buffer status
        """
        # Check for buffer underrun
        if status.output_underflow:
            self.underrun_count += 1
            print(f"[AudioEngine] UNDERRUN #{self.underrun_count}")
        
        try:
            # Generate mixed audio from all active voices
            samples = self.mixer.mix(frames)
            
            # Store samples in waveform buffer for oscilloscope visualization
            self._update_waveform_buffer(samples)
            
            # Output samples
            outdata[:, 0] = samples

            if self.recording_file is not None:
                self.recording_file.writeframes((samples * 0.8 * 32767).astype(np.int16).tobytes())
            
            # Track statistics
            self.sample_count += frames
            
        except Exception as e:
            # In case of error, output silence to prevent crashes
            print(f"[AudioEngine] ERROR in callback: {e}")
            outdata.fill(0)
    
    def _update_waveform_buffer(self, samples: np.ndarray) -> None:
        """
        Update the circular waveform buffer with new samples.
        
        Used by the oscilloscope widget for real-time visualization.
        
        Args:
            samples: New audio samples to add to buffer
        """
        with self.waveform_lock:
            # Calculate how much space is available in buffer
            available = len(self.waveform_buffer) - self.waveform_index
            
            if len(samples) <= available:
                # Samples fit in remaining space
                self.waveform_buffer[
                    self.waveform_index:self.waveform_index + len(samples)
                ] = samples
                self.waveform_index += len(samples)
            else:
                # Wrap around: fill remaining space and continue from start
                self.waveform_buffer[self.waveform_index:] = samples[:available]
                remaining = len(samples) - available
                self.waveform_buffer[:remaining] = samples[available:]
                self.waveform_index = remaining
    
    def get_waveform_buffer(self) -> np.ndarray:
        """
        Get a copy of the current waveform buffer.
        
        Safe to call from GUI thread.
        
        Returns:
            Copy of waveform buffer
        """
        with self.waveform_lock:
            return self.waveform_buffer.copy()
    
    def note_on(
        self,
        frequency: float,
        amplitude: float = 0.5,
        oscillator_type: str = 'sine'
    ) -> Optional:
        """
        Trigger a note on event.

        Thread-safe call from GUI.
        
        Args:
            frequency: Note frequency in Hz
            amplitude: Note amplitude [0, 1]
            oscillator_type: Waveform type
            
        Returns:
            Voice object ID for use with note_off, or None if no voices available
        """
        if self.is_running:
            return self.mixer.note_on(
                frequency=frequency,
                amplitude=amplitude,
                oscillator_type=oscillator_type
            )
        return None
    
    def note_off(self, voice=None) -> None:
        """
        Trigger a note off event (stop a specific voice).

        Thread-safe call from GUI.
        
        Args:
            voice: Voice returned by note_on(), or None to stop all voices
        """
        if self.is_running:
            if voice is None:
                self.mixer.stop_all()
            else:
                self.mixer.note_off(voice)

    def set_voice_frequency(self, voice, frequency: float) -> None:
        """Update the frequency of one active voice."""
        voice.set_frequency(frequency)

    def set_voice_amplitude(self, voice, amplitude: float) -> None:
        """Update the amplitude of one active voice."""
        voice.set_amplitude(amplitude)
    
    def set_master_volume(self, volume: float) -> None:
        """
        Set master volume level.
        
        Thread-safe call from GUI.
        
        Args:
            volume: Volume level [0, 1]
        """
        self.mixer.set_master_volume(volume)

    def set_distortion(self, effect: str, drive: float = 0.0, mix: float = 1.0) -> None:
        """Configure master distortion applied to the mixed voices."""
        self.mixer.set_distortion(effect, drive, mix)

    def set_delay(
        self,
        enabled: bool,
        time_ms: float = 250.0,
        feedback: float = 0.3,
        mix: float = 0.25,
    ) -> None:
        """Configure the master delay applied to the mixed voices."""
        self.mixer.set_delay(enabled, time_ms, feedback, mix)

    def set_chorus(
        self,
        enabled: bool,
        rate_hz: float = 0.8,
        depth_ms: float = 6.0,
        mix: float = 0.25,
    ) -> None:
        """Configure the master chorus applied to the mixed voices."""
        self.mixer.set_chorus(enabled, rate_hz, depth_ms, mix)

    def set_reverb(
        self,
        enabled: bool,
        decay_seconds: float = 1.8,
        mix: float = 0.3,
    ) -> None:
        """Configure the master reverb applied to the mixed voices."""
        self.mixer.set_reverb(enabled, decay_seconds, mix)
    
    def set_oscillator_type(self, osc_type: str) -> None:
        """
        Set oscillator type for all active voices.
        
        Thread-safe call from GUI.
        
        Args:
            osc_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        self.mixer.set_oscillator_type(osc_type)

    def load_sample(self, path: str, root_frequency: float = 440.0) -> None:
        """Load a WAV sample for all current and future notes."""
        self.mixer.load_sample(path, root_frequency)

    def clear_sample(self) -> None:
        self.mixer.clear_sample()

    def set_sample_root_frequency(self, frequency: float) -> None:
        self.mixer.set_sample_root_frequency(frequency)

    def set_adsr_parameters(
        self,
        attack_time: float = 0.01,
        decay_time: float = 0.1,
        sustain_level: float = 0.7,
        release_time: float = 0.3,
    ) -> None:
        """Update ADSR parameters for all active voices."""
        self.mixer.set_adsr_parameters(
            attack_time=attack_time,
            decay_time=decay_time,
            sustain_level=sustain_level,
            release_time=release_time,
        )

    def set_filter(self, kind: str, cutoff: float, resonance: float) -> None:
        """Update the filter settings for all active voices."""
        self.mixer.set_filter(kind=kind, cutoff=cutoff, resonance=resonance)

    def set_lfo_parameters(self, frequency: float = 0.0, depth: float = 0.0, target: str = 'pitch') -> None:
        """Update LFO modulation settings for all active voices."""
        self.mixer.set_lfo_parameters(frequency=frequency, depth=depth, target=target)
    
    def get_active_voice_count(self) -> int:
        """
        Get current number of active voices.
        
        Returns:
            Number of voices currently playing
        """
        return self.mixer.get_active_voice_count()
    
    def get_audio_info(self) -> dict:
        """
        Get audio engine information as a dictionary.
        
        Returns:
            Dictionary with engine status and statistics for GUI usage
        """
        return {
            "sample_rate": self.sample_rate,
            "buffer_size": self.buffer_size,
            "latency_ms": self.buffer_size * 1000 / self.sample_rate,
            "active_voices": self.get_active_voice_count(),
            "max_voices": self.max_voices,
            "underruns": self.underrun_count,
            "total_samples": self.sample_count,
        }

    def get_audio_info_text(self) -> str:
        """
        Get human-readable audio engine information.
        
        Returns:
            String with engine status and statistics
        """
        info = self.get_audio_info()
        return (
            f"Sample Rate: {info['sample_rate']} Hz\n"
            f"Buffer Size: {info['buffer_size']} samples\n"
            f"Latency: ~{info['latency_ms']:.1f} ms\n"
            f"Active Voices: {info['active_voices']}/{info['max_voices']}\n"
            f"Underruns: {info['underruns']}\n"
            f"Total Samples: {info['total_samples']}"
        )
    
    def start_recording(self, path: str) -> None:
        """Begin recording the mixed output to a WAV file."""
        if self.recording_file is not None:
            self.stop_recording()

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.recording_file = wave.open(str(output_path), 'wb')
        self.recording_file.setnchannels(1)
        self.recording_file.setsampwidth(2)
        self.recording_file.setframerate(self.sample_rate)
        self.recording_path = output_path

    def stop_recording(self) -> None:
        """Stop recording and close the current WAV file."""
        if self.recording_file is not None:
            self.recording_file.close()
            self.recording_file = None
            self.recording_path = None

    def list_devices(self) -> None:
        """Print available audio devices to console."""
        print("[AudioEngine] Available audio devices:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            print(f"  [{i}] {device['name']}")
