# -*- coding: utf-8 -*-
"""
Audio Engine module for the Muse Synthesizer.

The AudioEngine handles real-time audio I/O using sounddevice.
It manages a separate thread for audio processing to minimize latency
and prevent blocking of the GUI thread.

Key features:
- Real-time audio streaming at 44.1 kHz
- Configurable buffer size (256-512 samples)
- Separate audio thread for stable I/O
- Thread-safe communication with GUI
"""

from threading import Thread, Event, Lock, get_ident
from concurrent.futures import Future, TimeoutError
from queue import Empty, Full, Queue, SimpleQueue
from typing import Callable, Optional, Any
from pathlib import Path
from time import perf_counter_ns

import numpy as np
import sounddevice as sd
import wave

from audio.mixer import Mixer
from audio.voice import Voice


class VoiceHandle:
    """Non-blocking reference to a voice that is started inside the audio callback.

    AudioEngine.note_on() returns it immediately; the real Voice is attached when
    the callback processes the queued note-on. Operations queued afterwards
    (note_off, set_frequency, ...) always run later in the same FIFO queue, so
    they can safely rely on ``voice`` being resolved.
    """

    def __init__(self, frequency: float, amplitude: float) -> None:
        self.voice: Optional[Voice] = None
        self._frequency = frequency
        self._amplitude = amplitude

    # Executed in the audio callback thread ---------------------------------
    def start(self, mixer, frequency, amplitude, oscillator_type) -> None:
        self.voice = mixer.note_on(frequency, amplitude, oscillator_type)

    def stop(self, mixer) -> None:
        voice, self.voice = self.voice, None
        if voice is not None:
            mixer.note_off(voice)

    def set_frequency(self, frequency: float) -> None:
        self._frequency = frequency
        if self.voice is not None:
            self.voice.set_frequency(frequency)

    def set_amplitude(self, amplitude: float) -> None:
        self._amplitude = amplitude
        if self.voice is not None:
            self.voice.set_amplitude(amplitude)

    # Read-only mirrors, used by the GUI -------------------------------------
    @property
    def frequency(self) -> float:
        voice = self.voice
        return getattr(voice, "frequency", self._frequency) if voice is not None else self._frequency

    @property
    def amplitude(self) -> float:
        voice = self.voice
        return getattr(voice, "amplitude", self._amplitude) if voice is not None else self._amplitude


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

    CALLBACK_TIMING_WINDOW = 512
    
    def __init__(
        self,
        sample_rate: int = 44100,
        buffer_size: int = 512,
        max_voices: int = 32
    ) -> None:
        """
        Initialize the audio engine.
        
        Args:
            sample_rate: Audio sample rate in Hz (default: 44100)
            buffer_size: Samples per buffer (default: 512 = ~11.6ms latency)
            max_voices: Maximum simultaneous voices (default: 32)
        """
        self.sample_rate: int = sample_rate
        self.buffer_size: int = max(64, int(buffer_size))
        self.max_voices: int = max_voices
        
        # Create mixer for voice management
        self.mixer: Mixer = Mixer(
            max_voices=max_voices,
            sample_rate=sample_rate
        )
        self._pending_updates = SimpleQueue()
        self._update_batch: Optional[list] = None
        self._update_batch_owner: Optional[int] = None
        
        # Audio stream state
        self.stream: Optional[sd.OutputStream] = None
        self.is_running: bool = False
        
        # Thread management
        self.audio_thread: Optional[Thread] = None
        self.stop_event: Event = Event()
        
        # Circular buffer for waveform capture (for oscilloscope)
        self.waveform_buffer: np.ndarray = np.zeros(
            max(512, self.buffer_size), dtype=np.float32  # scope window independent of block size
        )  # ~46ms at 48kHz
        self.waveform_index: int = 0
        self.waveform_lock: Lock = Lock()
        
        # Performance metrics
        self.sample_count: int = 0
        self.underrun_count: int = 0
        self.callback_count: int = 0
        self.callback_time_total_ns: int = 0
        self.callback_time_max_ns: int = 0
        self.callback_deadline_misses: int = 0
        self._callback_times_ns = [0] * self.CALLBACK_TIMING_WINDOW
        self._callback_deadline_misses_window = [False] * self.CALLBACK_TIMING_WINDOW
        self._callback_window_deadline_misses = 0
        self._callback_times_index = 0
        self._callback_times_count = 0
        self._callback_budget_ns = 0
        self.recording_path: Optional[Path] = None
        self.recording_file: Optional[wave.Wave_write] = None
        self._recording_queue: Optional[Queue] = None
        self._recording_thread: Optional[Thread] = None
        self._recording_lock = Lock()
        self._recording_accepting = False
        self._recording_error: Optional[Exception] = None
        
    def start(self) -> None:
        """
        Start the audio engine and streaming thread.
        
        Initializes the audio device and begins real-time audio streaming.
        """
        if self.is_running:
            return
        
        try:
            self._reset_callback_metrics()
            # Create audio output stream
            # Using callback mode for real-time processing
            kwargs = dict(
                channels=1,  # Mono output
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                callback=self._audio_callback
            )
            try:
                wasapi = next(
                    (a for a in sd.query_hostapis() if "WASAPI" in a["name"]), None
                )
                if wasapi is None:
                    raise RuntimeError("WASAPI not available")
                self.stream = sd.OutputStream(
                    device=wasapi["default_output_device"],
                    extra_settings=sd.WasapiSettings(auto_convert=True),
                    **kwargs,
                )
            except Exception:
                self.stream = sd.OutputStream(**kwargs)
            
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
            raise RuntimeError(f"Unable to start audio stream: {e}") from e
    
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
            self._apply_pending_updates()
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
        callback_started_ns = perf_counter_ns()
        try:
            if status.output_underflow:
                self.underrun_count += 1

            self._apply_pending_updates()
            # Generate mixed audio from all active voices
            samples = self.mixer.mix(frames)
            
            # Store samples in waveform buffer for oscilloscope visualization
            self._update_waveform_buffer(samples)
            
            # Output samples
            outdata[:, 0] = samples

            if self.recording_file is not None:
                self._enqueue_recording_samples(samples)
            
            # Track statistics
            self.sample_count += frames
        except Exception as e:
            # In case of error, output silence to prevent crashes
            print(f"[AudioEngine] ERROR in callback: {e}")
            outdata.fill(0)
        finally:
            self._record_callback_timing(
                perf_counter_ns() - callback_started_ns,
                frames,
            )

    def _reset_callback_metrics(self) -> None:
        """Reset callback timing counters when a new audio stream starts."""
        self.callback_count = 0
        self.callback_time_total_ns = 0
        self.callback_time_max_ns = 0
        self.callback_deadline_misses = 0
        self._callback_times_ns[:] = [0] * self.CALLBACK_TIMING_WINDOW
        self._callback_deadline_misses_window[:] = (
            [False] * self.CALLBACK_TIMING_WINDOW
        )
        self._callback_window_deadline_misses = 0
        self._callback_times_index = 0
        self._callback_times_count = 0
        self._callback_budget_ns = 0
        self.underrun_count = 0

    def _record_callback_timing(self, elapsed_ns: int, frames: int) -> None:
        """Record one callback duration using a fixed-size rolling window."""
        self.callback_count += 1
        self.callback_time_total_ns += elapsed_ns
        if elapsed_ns > self.callback_time_max_ns:
            self.callback_time_max_ns = elapsed_ns

        budget_ns = frames * 1_000_000_000 // self.sample_rate
        self._callback_budget_ns = budget_ns
        deadline_missed = elapsed_ns > budget_ns
        if deadline_missed:
            self.callback_deadline_misses += 1

        index = self._callback_times_index
        self._callback_window_deadline_misses -= int(
            self._callback_deadline_misses_window[index]
        )
        self._callback_deadline_misses_window[index] = deadline_missed
        self._callback_window_deadline_misses += int(deadline_missed)
        self._callback_times_ns[index] = elapsed_ns
        self._callback_times_index = (
            index + 1
        ) % self.CALLBACK_TIMING_WINDOW
        self._callback_times_count = min(
            self._callback_times_count + 1,
            self.CALLBACK_TIMING_WINDOW,
        )

    def get_callback_performance(self) -> dict:
        """Return callback timing summaries; percentile work stays off the audio thread."""
        recent_times = sorted(
            self._callback_times_ns[:self._callback_times_count]
        )
        if recent_times:
            p95_index = max(0, int(np.ceil(0.95 * len(recent_times))) - 1)
            p95_ns = recent_times[p95_index]
        else:
            p95_ns = 0

        budget_ns = self._callback_budget_ns or (
            self.buffer_size * 1_000_000_000 // self.sample_rate
        )
        budget_ms = budget_ns / 1_000_000.0
        mean_ns = (
            self.callback_time_total_ns / self.callback_count
            if self.callback_count
            else 0.0
        )
        return {
            "callbacks": self.callback_count,
            "mean_ms": mean_ns / 1_000_000.0,
            "p95_ms": p95_ns / 1_000_000.0,
            "max_ms": self.callback_time_max_ns / 1_000_000.0,
            "budget_ms": budget_ms,
            "p95_budget_percent": (
                p95_ns / budget_ns * 100.0
                if budget_ns > 0
                else 0.0
            ),
            "deadline_misses": self.callback_deadline_misses,
            "recent_deadline_misses": self._callback_window_deadline_misses,
            "recent_deadline_miss_percent": (
                self._callback_window_deadline_misses
                / self._callback_times_count * 100.0
                if self._callback_times_count
                else 0.0
            ),
            "underruns": self.underrun_count,
            "window_size": self._callback_times_count,
        }

    def _update_mixer(self, method: str, *args, **kwargs) -> None:
        operation = getattr(self.mixer, method)
        self._queue_operation(operation, args, kwargs)

    def _queue_voice_update(self, voice, method: str, *args) -> None:
        operation = getattr(voice, method)
        self._queue_operation(operation, args)

    def _queue_operation(self, operation, args=(), kwargs=None, wait=False):
        kwargs = kwargs or {}
        if self._update_batch is not None and self._update_batch_owner == get_ident():
            self._update_batch.append((operation, args, kwargs))
            return None
        if not self.is_running or self.stream is None:
            return operation(*args, **kwargs)

        result = Future() if wait else None
        self._pending_updates.put((operation, args, kwargs, result))
        if result is None:
            return None
        try:
            return result.result(timeout=0.5)
        except TimeoutError as error:
            result.cancel()
            raise RuntimeError("Audio callback did not accept the note in time") from error

    def _apply_pending_updates(self) -> None:
        while True:
            try:
                operation, args, kwargs, result = self._pending_updates.get_nowait()
            except Empty:
                return
            if result is not None and result.cancelled():
                continue
            try:
                value = operation(*args, **kwargs)
            except Exception as error:
                if result is None:
                    raise
                if not result.cancelled():
                    result.set_exception(error)
            else:
                if result is not None and not result.cancelled():
                    result.set_result(value)

    def begin_update_batch(self) -> None:
        if self._update_batch is not None:
            raise RuntimeError("An audio update batch is already active")
        self._update_batch = []
        self._update_batch_owner = get_ident()

    def commit_update_batch(self) -> None:
        if self._update_batch is None or self._update_batch_owner != get_ident():
            raise RuntimeError("No audio update batch belongs to this thread")
        updates = self._update_batch
        self._update_batch = None
        self._update_batch_owner = None

        def apply_batch() -> None:
            for operation, args, kwargs in updates:
                operation(*args, **kwargs)

        if updates:
            self._queue_operation(apply_batch)

    def cancel_update_batch(self) -> None:
        if self._update_batch is None or self._update_batch_owner != get_ident():
            raise RuntimeError("No audio update batch belongs to this thread")
        self._update_batch = None
        self._update_batch_owner = None
    
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
        oscillator_type: Optional[str] = None
    ) -> Optional[Voice]:
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
        if not self.is_running:
            return None
        if self.stream is None:
            return self._queue_operation(
                self.mixer.note_on, (frequency, amplitude, oscillator_type)
            )
        # Do not block the GUI thread waiting for the audio callback: return a
        # handle now, the callback attaches the real voice at the next block.
        handle = VoiceHandle(frequency, amplitude)
        self._queue_operation(
            handle.start, (self.mixer, frequency, amplitude, oscillator_type)
        )
        return handle
    
    def note_off(self, voice=None) -> None:
        """
        Trigger a note off event (stop a specific voice).

        Thread-safe call from GUI.
        
        Args:
            voice: Voice returned by note_on(), or None to stop all voices
        """
        if self.is_running:
            if voice is None:
                operation = self.mixer.stop_all
            elif isinstance(voice, VoiceHandle):
                self._queue_operation(voice.stop, (self.mixer,))
                return
            else:
                operation = self.mixer.note_off
                self._queue_operation(operation, (voice,))
                return
            self._queue_operation(operation)

    def set_voice_frequency(self, voice, frequency: float) -> None:
        """Update the frequency of one active voice."""
        self._queue_voice_update(voice, 'set_frequency', frequency)

    def set_voice_amplitude(self, voice, amplitude: float) -> None:
        """Update the amplitude of one active voice."""
        self._queue_voice_update(voice, 'set_amplitude', amplitude)
    
    def set_master_volume(self, volume: float) -> None:
        """
        Set master volume level.
        
        Thread-safe call from GUI.
        
        Args:
            volume: Volume level [0, 1]
        """
        self._update_mixer('set_master_volume', volume)

    def set_distortion(self, effect: str, drive: float = 0.0, mix: float = 1.0) -> None:
        """Configure master distortion applied to the mixed voices."""
        self._update_mixer('set_distortion', effect, drive, mix)

    def set_delay(
        self,
        enabled: bool,
        time_ms: float = 250.0,
        feedback: float = 0.3,
        mix: float = 0.25,
    ) -> None:
        """Configure the master delay applied to the mixed voices."""
        self._update_mixer('set_delay', enabled, time_ms, feedback, mix)

    def set_chorus(
        self,
        enabled: bool,
        rate_hz: float = 0.8,
        depth_ms: float = 6.0,
        mix: float = 0.25,
    ) -> None:
        """Configure the master chorus applied to the mixed voices."""
        self._update_mixer('set_chorus', enabled, rate_hz, depth_ms, mix)

    def set_reverb(
        self,
        enabled: bool,
        decay_seconds: float = 1.8,
        mix: float = 0.3,
    ) -> None:
        """Configure the master reverb applied to the mixed voices."""
        self._update_mixer('set_reverb', enabled, decay_seconds, mix)
    
    def set_oscillator_type(self, osc_type: str) -> None:
        """
        Set oscillator type for all active voices.
        
        Thread-safe call from GUI.
        
        Args:
            osc_type: Waveform type ('sine', 'square', 'triangle', 'sawtooth')
        """
        self._update_mixer('set_oscillator_type', osc_type)

    def set_unison_parameters(self, voices: int = 1, detune_cents: float = 0.0) -> None:
        """Configure oscillator stacking and detune for active and future notes."""
        self._update_mixer('set_unison_parameters', voices, detune_cents)

    def set_synthesis_mode(self, mode: str) -> None:
        """Select waveform, additive, or FM synthesis."""
        self._update_mixer('set_synthesis_mode', mode)

    def set_synthesis_parameters(
        self,
        additive_partials: int = 8,
        additive_tilt_db_per_octave: float = 6.0,
        fm_ratio: float = 2.0,
        fm_index: float = 2.0,
    ) -> None:
        """Configure additive and FM controls for active and future notes."""
        self._update_mixer(
            'set_synthesis_parameters',
            additive_partials,
            additive_tilt_db_per_octave,
            fm_ratio,
            fm_index,
        )

    def load_sample(self, path: str, root_frequency: float = 440.0) -> None:
        """Decode a WAV sample outside the callback, then install it at a block boundary."""
        prepared_sample = Voice(sample_rate=self.sample_rate)
        prepared_sample.load_sample(path, root_frequency)
        self._update_mixer(
            'install_sample',
            prepared_sample.sample,
            prepared_sample.sample_path,
            prepared_sample.sample_root_frequency,
        )

    def clear_sample(self) -> None:
        self._update_mixer('clear_sample')

    def set_sample_root_frequency(self, frequency: float) -> None:
        self._update_mixer('set_sample_root_frequency', frequency)

    def set_buffer_size(self, size: int) -> None:
        if self.is_running:
            raise RuntimeError("Stop the audio engine before changing the buffer size")
        if size < 64:
            raise ValueError("Buffer size must be at least 64 samples")
        self.buffer_size = int(size)

    def set_sample_rate(self, sample_rate: int) -> None:
        if self.is_running:
            raise RuntimeError("Stop the audio engine before changing the sample rate")
        if self.recording_file is not None:
            raise RuntimeError("Stop recording before changing the sample rate")
        if sample_rate < 8000 or sample_rate > 192000:
            raise ValueError("Sample rate must be between 8000 and 192000 Hz")
        sample_rate = int(sample_rate)
        if sample_rate == self.sample_rate:
            return

        old_mixer = self.mixer
        new_mixer = Mixer(max_voices=self.max_voices, sample_rate=sample_rate)
        new_mixer.voice_settings.update(old_mixer.voice_settings)
        new_mixer.set_master_volume(old_mixer.master_volume)
        new_mixer.set_distortion(
            old_mixer.distortion_type,
            old_mixer.distortion_drive,
            old_mixer.distortion_mix,
        )
        new_mixer.set_delay(
            old_mixer.delay_enabled,
            old_mixer.delay_time_ms,
            old_mixer.delay_feedback,
            old_mixer.delay_mix,
        )
        new_mixer.set_chorus(
            old_mixer.chorus_enabled,
            old_mixer.chorus_rate_hz,
            old_mixer.chorus_depth_ms,
            old_mixer.chorus_mix,
        )
        new_mixer.set_reverb(
            old_mixer.reverb.enabled,
            old_mixer.reverb.decay_seconds,
            old_mixer.reverb.mix,
        )

        sample_path = old_mixer.voices[0].sample_path
        if sample_path is not None:
            new_mixer.load_sample(
                sample_path,
                old_mixer.voice_settings['sample_root_frequency'],
            )

        self.sample_rate = sample_rate
        self.mixer = new_mixer
        with self.waveform_lock:
            self.waveform_buffer = np.zeros(
                max(512, self.buffer_size), dtype=np.float32
            )
            self.waveform_index = 0

    def set_adsr_parameters(
        self,
        attack_time: float = 0.01,
        decay_time: float = 0.1,
        sustain_level: float = 0.7,
        release_time: float = 0.3,
    ) -> None:
        """Update ADSR parameters for all active voices."""
        self._update_mixer(
            'set_adsr_parameters',
            attack_time=attack_time,
            decay_time=decay_time,
            sustain_level=sustain_level,
            release_time=release_time,
        )

    def set_filter(self, kind: str, cutoff: float, resonance: float) -> None:
        """Update the filter settings for all active voices."""
        self._update_mixer(
            'set_filter', kind=kind, cutoff=cutoff, resonance=resonance
        )

    def set_lfo_parameters(self, frequency: float = 0.0, depth: float = 0.0, target: str = 'pitch') -> None:
        """Update LFO modulation settings for all active voices."""
        self._update_mixer(
            'set_lfo_parameters', frequency=frequency, depth=depth, target=target
        )
    
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
        callback_performance = self.get_callback_performance()
        return {
            "sample_rate": self.sample_rate,
            "buffer_size": self.buffer_size,
            "latency_ms": self.buffer_size * 1000 / self.sample_rate,
            "active_voices": self.get_active_voice_count(),
            "max_voices": self.max_voices,
            "underruns": self.underrun_count,
            "total_samples": self.sample_count,
            "callback_mean_ms": callback_performance["mean_ms"],
            "callback_p95_ms": callback_performance["p95_ms"],
            "callback_max_ms": callback_performance["max_ms"],
            "callback_budget_ms": callback_performance["budget_ms"],
            "callback_p95_budget_percent": callback_performance[
                "p95_budget_percent"
            ],
            "callback_deadline_misses": callback_performance["deadline_misses"],
            "callback_recent_deadline_misses": callback_performance[
                "recent_deadline_misses"
            ],
            "callback_recent_deadline_miss_percent": callback_performance[
                "recent_deadline_miss_percent"
            ],
            "callback_window_size": callback_performance["window_size"],
            "callback_count": callback_performance["callbacks"],
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
            f"Callback mean/P95/max: {info['callback_mean_ms']:.3f}/"
            f"{info['callback_p95_ms']:.3f}/{info['callback_max_ms']:.3f} ms\n"
            f"Callback budget: {info['callback_budget_ms']:.3f} ms "
            f"(recent {info['callback_recent_deadline_misses']}/"
            f"{info['callback_window_size']}, "
            f"{info['callback_recent_deadline_miss_percent']:.1f}%; "
            f"{info['callback_deadline_misses']} total misses)\n"
            f"Total Samples: {info['total_samples']}"
        )
    
    def start_recording(self, path: str) -> None:
        """Begin recording the mixed output to a WAV file."""
        if self.recording_file is not None:
            previous_error = self.stop_recording()
            if previous_error is not None:
                raise RuntimeError(
                    f"Previous recording failed: {previous_error}"
                ) from previous_error

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        recording_file = wave.open(str(output_path), 'wb')
        try:
            recording_file.setnchannels(1)
            recording_file.setsampwidth(2)
            recording_file.setframerate(self.sample_rate)
        except Exception:
            recording_file.close()
            raise

        recording_queue: Queue = Queue(maxsize=64)
        recording_thread = Thread(
            target=self._write_recording,
            args=(recording_queue, recording_file),
            name="AudioRecordingWriter",
            daemon=True,
        )
        with self._recording_lock:
            self.recording_file = recording_file
            self.recording_path = output_path
            self._recording_queue = recording_queue
            self._recording_thread = recording_thread
            self._recording_accepting = True
            self._recording_error = None
        try:
            recording_thread.start()
        except Exception:
            with self._recording_lock:
                self.recording_file = None
                self.recording_path = None
                self._recording_queue = None
                self._recording_thread = None
                self._recording_accepting = False
            recording_file.close()
            raise

    def _enqueue_recording_samples(self, samples: np.ndarray) -> None:
        with self._recording_lock:
            recording_queue = self._recording_queue
            if recording_queue is None or not self._recording_accepting:
                return

            pcm_samples = np.clip(
                samples * (0.8 * 32767.0), -32768, 32767
            ).astype("<i2").tobytes()
            try:
                recording_queue.put_nowait(pcm_samples)
            except Full:
                self._recording_accepting = False
                self._recording_error = RuntimeError(
                    "Recording stopped because the disk writer could not "
                    "keep up with audio output."
                )

    def _write_recording(
        self,
        recording_queue: Queue,
        recording_file: wave.Wave_write,
    ) -> None:
        write_error: Optional[Exception] = None
        while True:
            pcm_samples = recording_queue.get()
            if pcm_samples is None:
                break
            if write_error is None:
                try:
                    recording_file.writeframes(pcm_samples)
                except Exception as error:
                    write_error = error

        try:
            recording_file.close()
        except Exception as error:
            if write_error is None:
                write_error = error

        if write_error is not None:
            with self._recording_lock:
                if self._recording_error is None:
                    self._recording_error = write_error

    def stop_recording(self) -> Optional[Exception]:
        """Stop recording, flush queued audio, and return any recording error."""
        with self._recording_lock:
            recording_queue = self._recording_queue
            recording_thread = self._recording_thread
            self._recording_accepting = False
            self.recording_file = None
            self.recording_path = None

        if recording_queue is not None and recording_thread is not None:
            recording_queue.put(None)
            recording_thread.join()

        with self._recording_lock:
            error = self._recording_error
            self._recording_queue = None
            self._recording_thread = None
            self._recording_error = None
        return error

    def list_devices(self) -> None:
        """Print available audio devices to console."""
        print("[AudioEngine] Available audio devices:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            print(f"  [{i}] {device['name']}")