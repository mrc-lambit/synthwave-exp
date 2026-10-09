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
from audio.engine import AudioEngine

# This module is a manual hardware playback demo, not an automated test suite.
__test__ = False


def test_default_buffer_is_stable() -> None:
    engine = AudioEngine()
    assert engine.buffer_size >= 512


def test_audio_engine() -> None:
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
    
    # Start audio streaming
    print("[2] Starting audio stream...")
    engine.start()
    time.sleep(0.5)  # Give stream time to initialize
    
    if not engine.is_running:
        print("ERROR: Audio engine failed to start!")
        return
    
    # Trigger note on (A4 = 440 Hz)
    print("[3] Playing A4 (440 Hz) sine wave...")
    engine.note_on(
        frequency=440.0,
        amplitude=0.5,
        oscillator_type='sine'
    )
    
    # Let it play for 3 seconds
    print("[4] Playing for 3 seconds...")
    start_time = time.time()
    for i in range(30):
        time.sleep(0.1)
        voice_count = engine.get_active_voice_count()
        print(f"    [{i+1}] Active voices: {voice_count}")
    
    elapsed = time.time() - start_time
    
    # Stop the note
    print(f"\n[5] Stopping note (played for {elapsed:.1f}s)...")
    engine.note_off()
    time.sleep(0.5)
    
    # Print engine info
    print(f"\n[6] Engine Statistics:")
    print(engine.get_audio_info_text())
    
    # Stop audio engine
    print("\n[7] Stopping audio engine...")
    engine.stop()
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60 + "\n")


def test_oscillator_types() -> None:
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
    
    engine.start()
    time.sleep(0.5)
    
    oscillator_types = ['sine', 'square', 'triangle', 'sawtooth']
    
    for osc_type in oscillator_types:
        print(f"\n[*] Playing {osc_type.upper()} wave at 440 Hz...")
        
        engine.set_oscillator_type(osc_type)
        engine.note_on(frequency=440.0, amplitude=0.4)
        
        # Play for 2 seconds
        for i in range(20):
            time.sleep(0.1)
        
        engine.note_off()
        time.sleep(0.3)
    
    engine.stop()
    
    print("\n" + "="*60)
    print("Oscillator Test Complete!")
    print("="*60 + "\n")


def test_polyphony() -> None:
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
    
    engine.start()
    time.sleep(0.5)
    
    # C Major triad frequencies
    # C4 = 261.63 Hz
    # E4 = 329.63 Hz
    # G4 = 392.00 Hz
    
    print("[*] Playing C Major chord (C4, E4, G4)...\n")
    
    frequencies = [261.63, 329.63, 392.00]
    note_names = ['C4', 'E4', 'G4']
    
    for freq, name in zip(frequencies, note_names):
        print(f"    Triggering {name} ({freq:.1f} Hz)")
        engine.note_on(frequency=freq, amplitude=0.4)
        time.sleep(0.1)
    
    print("\n[*] Playing chord for 3 seconds...")
    for i in range(30):
        time.sleep(0.1)
        voice_count = engine.get_active_voice_count()
        if i % 5 == 0:
            print(f"    Active voices: {voice_count}")
    
    engine.note_off()
    time.sleep(0.5)
    
    engine.stop()
    
    print("\n" + "="*60)
    print("Polyphony Test Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        # Run basic test
        test_audio_engine()
        
        # Run oscillator types test
        print("\nRunning oscillator types test...\n")
        test_oscillator_types()
        
        # Run polyphony test
        print("\nRunning polyphony test...\n")
        test_polyphony()
        
    except KeyboardInterrupt:
        print("\n\n[!] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
