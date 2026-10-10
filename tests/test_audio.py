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

import time
import pytest
from audio.engine import AudioEngine


def test_default_buffer_is_stable() -> None:
    engine = AudioEngine()
    assert engine.buffer_size >= 512


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
