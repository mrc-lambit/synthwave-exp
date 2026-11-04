#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for MUSA audio engine.

Generates a simple A4 note (440 Hz) for 3 seconds to verify:
- Audio engine initialization
- Real-time audio playback
- Voice generation
- Mixer output

Run with: python test_audio.py
"""

import json
import time
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import numpy as np
import pytest
from audio.engine import AudioEngine
from audio.mixer import Mixer

def test_default_buffer_is_stable() -> None:
    engine = AudioEngine()
    assert engine.buffer_size >= 512


def test_hand_resonant_polyphony_stays_below_output_peak_limit() -> None:
    preset_path = Path(__file__).parent.parent / 'presets' / 'hand-resonant.json'
    preset = json.loads(preset_path.read_text(encoding='utf-8'))
    mixer = Mixer(max_voices=12, sample_rate=44100)

    mixer.set_oscillator_type(preset['waveform'])
    mixer.set_master_volume(preset['master_volume'])
    mixer.set_distortion(**preset['distortion'])
    mixer.set_delay(**preset['delay'])
    mixer.set_chorus(**preset['chorus'])
    mixer.set_reverb(**preset['reverb'])
    mixer.set_adsr_parameters(
        preset['adsr']['attack'],
        preset['adsr']['decay'],
        preset['adsr']['sustain'],
        preset['adsr']['release'],
    )
    mixer.set_filter(
        preset['filter']['kind'],
        preset['filter']['cutoff'],
        preset['filter']['resonance'],
    )
    mixer.set_lfo_parameters(
        preset['lfo']['frequency'],
        preset['lfo']['depth'],
        preset['lfo']['target'],
    )
    for _ in range(12):
        mixer.note_on(440.0)

    output = np.concatenate([mixer.mix(512) for _ in range(10)])

    assert np.isfinite(output).all()
    assert np.max(np.abs(output)) <= mixer.OUTPUT_PEAK_LIMIT
    assert mixer._output_limiter_gain < 1.0


def test_start_failure_is_reported(monkeypatch) -> None:
    def fail_to_open_stream(**kwargs):
        raise OSError("no output device")

    monkeypatch.setattr('audio.engine.sd.OutputStream', fail_to_open_stream)
    engine = AudioEngine()

    with pytest.raises(RuntimeError, match="no output device"):
        engine.start()

    assert not engine.is_running
    assert engine.stream is None


def test_callback_performance_metrics_compare_work_with_buffer_budget(monkeypatch) -> None:
    engine = AudioEngine(sample_rate=48000, buffer_size=480, max_voices=1)
    timestamps = iter([
        1_000_000, 6_000_000,
        7_000_000, 19_000_000,
    ])
    monkeypatch.setattr('audio.engine.perf_counter_ns', lambda: next(timestamps))

    for underflow in (False, True):
        output = np.zeros((480, 1), dtype=np.float32)
        engine._audio_callback(
            output,
            480,
            None,
            SimpleNamespace(output_underflow=underflow),
        )

    metrics = engine.get_callback_performance()

    assert metrics['callbacks'] == 2
    assert metrics['mean_ms'] == pytest.approx(8.5)
    assert metrics['p95_ms'] == pytest.approx(12.0)
    assert metrics['max_ms'] == pytest.approx(12.0)
    assert metrics['budget_ms'] == pytest.approx(10.0)
    assert metrics['p95_budget_percent'] == pytest.approx(120.0)
    assert metrics['deadline_misses'] == 1
    assert metrics['underruns'] == 1


def test_callback_timing_uses_a_bounded_recent_window() -> None:
    engine = AudioEngine(sample_rate=1000, buffer_size=64)
    engine.CALLBACK_TIMING_WINDOW = 3
    engine._callback_times_ns = [0] * engine.CALLBACK_TIMING_WINDOW

    for elapsed in (1_000_000, 12_000_000, 3_000_000, 14_000_000):
        engine._record_callback_timing(elapsed, 10)

    metrics = engine.get_callback_performance()

    assert metrics['callbacks'] == 4
    assert metrics['window_size'] == 3
    assert metrics['mean_ms'] == pytest.approx(7.5)
    assert metrics['p95_ms'] == pytest.approx(14.0)
    assert metrics['max_ms'] == pytest.approx(14.0)
    assert metrics['deadline_misses'] == 2
    assert metrics['recent_deadline_misses'] == 2
    assert metrics['recent_deadline_miss_percent'] == pytest.approx(200 / 3)


def test_new_voice_inherits_current_mixer_settings() -> None:
    mixer = Mixer(max_voices=1)
    mixer.set_oscillator_type('triangle')
    mixer.set_adsr_parameters(0.2, 0.3, 0.4, 0.5)
    mixer.set_filter('highpass', 1800.0, 0.25)
    mixer.set_lfo_parameters(3.0, 0.6, 'filter')
    mixer.set_sample_root_frequency(220.0)

    voice = mixer.note_on(440.0)

    assert voice.oscillator_type == 'triangle'
    assert voice.envelope.attack_samples == int(0.2 * mixer.sample_rate)
    assert voice.envelope.decay_samples == int(0.3 * mixer.sample_rate)
    assert voice.envelope.sustain_level == 0.4
    assert voice.envelope.release_samples == int(0.5 * mixer.sample_rate)
    assert voice.filter.kind == 'highpass'
    assert voice.filter.cutoff == 1800.0
    assert voice.filter.resonance == 0.25
    assert voice.lfo.frequency == 3.0
    assert voice.lfo.depth == 0.6
    assert voice.lfo_target == 'filter'
    assert voice.sample_root_frequency == 220.0


def test_engine_applies_live_updates_at_next_audio_block() -> None:
    engine = AudioEngine(max_voices=1)
    voice = engine.mixer.note_on(440.0)
    engine.stream = object()
    engine.is_running = True

    engine.set_filter('highpass', 1200.0, 0.3)
    assert voice.filter.kind == 'lowpass'

    output = np.zeros((512, 1), dtype=np.float32)
    engine._audio_callback(output, 512, None, SimpleNamespace(output_underflow=False))

    assert voice.filter.kind == 'highpass'
    assert voice.filter.cutoff == 1200.0
    assert output.any()
    engine.is_running = False


def test_note_started_after_setting_change_is_audible() -> None:
    engine = AudioEngine(max_voices=1)
    engine.is_running = True
    engine.set_filter('highpass', 1200.0, 0.3)
    voice = engine.note_on(440.0, oscillator_type='sine')
    output = np.zeros((512, 1), dtype=np.float32)

    engine._audio_callback(
        output, 512, None, SimpleNamespace(output_underflow=False)
    )

    assert voice.filter.kind == 'highpass'
    assert output.any()
    engine.is_running = False


def test_note_lifecycle_is_processed_by_audio_callback() -> None:
    engine = AudioEngine(max_voices=1)
    engine.stream = object()
    engine.is_running = True
    voices = []
    note_thread = Thread(
        target=lambda: voices.append(engine.note_on(440.0, oscillator_type='sine'))
    )
    note_thread.start()
    deadline = time.monotonic() + 0.5
    while engine._pending_updates.empty() and time.monotonic() < deadline:
        time.sleep(0.001)

    output = np.zeros((512, 1), dtype=np.float32)
    status = SimpleNamespace(output_underflow=False)
    engine._audio_callback(output, 512, None, status)
    note_thread.join(timeout=0.5)

    assert not note_thread.is_alive()
    voice = voices[0]
    assert voice.is_active
    assert output.any()

    engine.note_off(voice)
    assert voice.is_active
    engine._audio_callback(output, 512, None, status)
    assert not voice.is_active
    engine.is_running = False
    engine.stream = None


def test_audio_demo_stops_engine_after_playback_error(monkeypatch) -> None:
    class FakeEngine:
        is_running = True
        stopped = False

        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

        def note_on(self, **kwargs):
            raise RuntimeError("simulated playback failure")

        def stop(self):
            self.stopped = True

    fake_engine = FakeEngine()
    monkeypatch.setattr('test_audio.AudioEngine', lambda **kwargs: fake_engine)
    monkeypatch.setattr('test_audio.time.sleep', lambda _seconds: None)

    with pytest.raises(RuntimeError, match="simulated playback failure"):
        run_audio_engine_demo()

    assert fake_engine.stopped


def run_audio_engine_demo() -> None:
    """
    Test the audio engine by generating an A4 note.
    
    A4 = 440 Hz (standard tuning frequency)
    """
    print("\n" + "="*60)
    print("MUSA Audio Engine Test")
    print("="*60 + "\n")
    
    # Create audio engine instance
    print("[1] Creating audio engine...")
    engine = AudioEngine(
        sample_rate=44100,
        buffer_size=256,
        max_voices=32
    )
    
    try:
        print("[2] Starting audio stream...")
        engine.start()
        time.sleep(0.5)

        if not engine.is_running:
            print("ERROR: Audio engine failed to start!")
            return

        print("[3] Playing A4 (440 Hz) sine wave...")
        voice = engine.note_on(frequency=440.0, amplitude=0.5, oscillator_type='sine')

        print("[4] Playing for 3 seconds...")
        start_time = time.time()
        for i in range(30):
            time.sleep(0.1)
            voice_count = engine.get_active_voice_count()
            print(f"    [{i+1}] Active voices: {voice_count}")

        elapsed = time.time() - start_time
        print(f"\n[5] Stopping note (played for {elapsed:.1f}s)...")
        if voice is not None:
            engine.note_off(voice)
        time.sleep(0.5)

        print("\n[6] Engine Statistics:")
        print(engine.get_audio_info_text())
    finally:
        print("\n[7] Stopping audio engine...")
        engine.stop()
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60 + "\n")


def run_oscillator_types_demo() -> None:
    """
    Test different oscillator types by playing them sequentially.
    """
    print("\n" + "="*60)
    print("MUSA Oscillator Types Test")
    print("="*60 + "\n")
    
    engine = AudioEngine(
        sample_rate=44100,
        buffer_size=256,
        max_voices=32
    )
    
    try:
        engine.start()
        time.sleep(0.5)
        if not engine.is_running:
            print("ERROR: Audio engine failed to start!")
            return

        oscillator_types = ['sine', 'square', 'triangle', 'sawtooth']
        for osc_type in oscillator_types:
            print(f"\n[*] Playing {osc_type.upper()} wave at 440 Hz...")
            engine.set_oscillator_type(osc_type)
            voice = engine.note_on(frequency=440.0, amplitude=0.4)
            for _ in range(20):
                time.sleep(0.1)
            if voice is not None:
                engine.note_off(voice)
            time.sleep(0.3)
    finally:
        engine.stop()
    
    print("\n" + "="*60)
    print("Oscillator Test Complete!")
    print("="*60 + "\n")


def run_polyphony_demo() -> None:
    """
    Test polyphony by playing a simple chord (C4, E4, G4).
    """
    print("\n" + "="*60)
    print("MUSA Polyphony Test (C Major Chord)")
    print("="*60 + "\n")
    
    engine = AudioEngine(
        sample_rate=44100,
        buffer_size=256,
        max_voices=32
    )
    
    voices = []
    try:
        engine.start()
        time.sleep(0.5)
        if not engine.is_running:
            print("ERROR: Audio engine failed to start!")
            return

        print("[*] Playing C Major chord (C4, E4, G4)...\n")
        frequencies = [261.63, 329.63, 392.00]
        note_names = ['C4', 'E4', 'G4']
        for frequency, name in zip(frequencies, note_names):
            print(f"    Triggering {name} ({frequency:.1f} Hz)")
            voice = engine.note_on(frequency=frequency, amplitude=0.4)
            if voice is not None:
                voices.append(voice)
            time.sleep(0.1)

        print("\n[*] Playing chord for 3 seconds...")
        for index in range(30):
            time.sleep(0.1)
            voice_count = engine.get_active_voice_count()
            if index % 5 == 0:
                print(f"    Active voices: {voice_count}")

        for voice in voices:
            engine.note_off(voice)
        time.sleep(0.5)
    finally:
        engine.stop()
    
    print("\n" + "="*60)
    print("Polyphony Test Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        # Run basic test
        run_audio_engine_demo()
        
        # Run oscillator types test
        print("\nRunning oscillator types test...\n")
        run_oscillator_types_demo()
        
        # Run polyphony test
        print("\nRunning polyphony test...\n")
        run_polyphony_demo()
        
    except KeyboardInterrupt:
        print("\n\n[!] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
