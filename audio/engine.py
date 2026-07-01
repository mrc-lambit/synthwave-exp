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

import numpy as np
import sounddevice as sd

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
    
    def stop(self) -> None:
        """
        Stop the audio engine and stream.
        
        Safely closes the audio stream and stops processing.
        """
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Stop all voices immediately
        self.mixer.stop_all()
        
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
    
    def note_off(self, voice) -> None:
        """
        Trigger a note off event (stop a specific voice).

        Thread-safe call from GUI.
        
        Args:
            voice: Voice object returned by note_on()
        """
        if self.is_running:
            self.mixer.note_off(voice)
    
    def set_master_volume(self, volume: float) -> None:
        """
        Set master volume level.
        
        Thread-safe call from GUI.
        
        Args:
            volume: Volume level [0, 1]
        """
        self.mixer.set_master_volume(volume)
    
    def set_oscillator_type(self, osc_type: str) -> None:
        """
        Set oscillator type for all active voices.
        
        Thread-safe call from GUI.
        
        Args:
            osc_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        self.mixer.set_oscillator_type(osc_type)
    
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
    
    def list_devices(self) -> None:
        """Print available audio devices to console."""
        print("[AudioEngine] Available audio devices:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            print(f"  [{i}] {device['name']}")
