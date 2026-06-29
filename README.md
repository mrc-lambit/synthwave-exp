# MUSA - Software Synthesizer

A desktop application for **mathematically-generated real-time audio synthesis** built with Python, PyQt6, and NumPy.

## Overview

MUSA is a prototype software synthesizer that generates all audio entirely through DSP (Digital Signal Processing). No pre-recorded samples are used. The application features:

- **4 Basic Oscillators**: Sine, Square, Triangle, Sawtooth
- **32-Voice Polyphony**: Play up to 32 notes simultaneously
- **Real-time Audio Generation**: 44.1 kHz sample rate with low-latency output
- **ADSR Envelope**: Control note attack, decay, sustain, release
- **Multiple Filters**: Low-pass, High-pass, Band-pass
- **LFO Modulation**: Modulate pitch, volume, and filter cutoff
- **Real-time Visualization**: Oscilloscope and FFT spectrum analyzer
- **PC Keyboard Input**: 48-note keyboard mapped to QWERTY layout
- **Harmonic Modes**: Single notes, dyads, and triads
- **6 Instrument Presets**: Piano, Organ, Flute, Violin, Clarinet, Synth Lead

## Requirements

- Python 3.8+
- PyQt6
- NumPy
- sounddevice
- pyqtgraph

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Run the Application

```bash
python main.py
```

### PC Keyboard Mapping

The synthesizer maps the PC QWERTY keyboard to a piano layout (2 active octaves, 24 notes):

**Upper Octave (Row 1):**
```
Z  S  X  D  C  V  G  B  H  N  J  M
C5 D5 E5 F5 G5 A5 B5 C6 D6 E6 F6 G6
```

**Lower Octave (Row 2):**
```
Q  2  W  3  E  R  5  T  6  Y  7  U
C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5
```

Both octaves are active simultaneously, allowing for richer polyphonic playing.

## Project Structure

```
musa-test/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── gui/                    # User interface
│   ├── main_window.py      # Main application window
│   ├── keyboard_widget.py  # Visual keyboard
│   ├── oscilloscope.py     # Real-time waveform display
│   └── spectrum_widget.py  # FFT analyzer
│
├── audio/                  # Audio engine & DSP
│   ├── engine.py           # Real-time audio playback
│   ├── oscillator.py       # Waveform generators
│   ├── voice.py            # Single voice/note handler
│   ├── mixer.py            # Polyphonic mixer
│   ├── envelope.py         # ADSR implementation
│   ├── filter.py           # Filter implementations
│   ├── lfo.py              # LFO modulation
│   └── effects.py          # Audio effects (future)
│
├── instruments/            # Instrument definitions
│   ├── instrument.py       # Instrument base class
│   └── presets.py          # Preset definitions
│
└── core/                   # Utility & core logic
    ├── note_mapper.py      # MIDI note helpers
    └── chord_engine.py     # Chord generation
```

## Architecture

### Audio Engine

- **Sample Rate**: 44100 Hz
- **Buffer Size**: 256-512 samples (~12ms latency)
- **Polyphony**: 32 voices
- **Threading**: Separate GUI and audio threads for stability

### Voice System

Each voice contains:
- Oscillator with selectable waveform
- ADSR envelope
- Frequency and phase state
- Active/inactive status

### Synthesizer Chain

```
Note Input → Oscillator → ADSR Envelope → Filter → LFO → Mixer → Output
```

## Features

### Oscillators

| Type | Characteristics |
|------|-----------------|
| **Sine** | Pure, smooth tone; no harmonics |
| **Square** | Bright, hollow; odd harmonics only |
| **Triangle** | Warm, mellow; odd harmonics (attenuated) |
| **Sawtooth** | Bright, buzzy; all harmonics |

### Keyboard & Polyphony

- **2 Active Octaves**: 24 notes simultaneously accessible (C4 to B5)
- **Polyphonic**: Up to 32 voices can play at once
- **PC Keyboard Input**: QWERTY layout mapped to piano keys
- **Simultaneous Octaves**: Both octave ranges playable at the same time for richer textures

### ADSR Envelope

- **Attack**: Time to reach peak amplitude
- **Decay**: Time to reach sustain level
- **Sustain**: Held amplitude level
- **Release**: Time to fade out after note ends

### Filters

- **Low-Pass**: Removes high frequencies
- **High-Pass**: Removes low frequencies
- **Band-Pass**: Isolates a frequency range

### LFO Modulation

Configurable LFO can modulate:
- Pitch (vibrato effect)
- Volume (tremolo effect)
- Filter cutoff (filter sweep effect)

### Visualization

- **Oscilloscope**: Real-time waveform display
- **FFT Spectrum**: Frequency domain analysis with harmonic visualization

## Presets

The application comes with 6 instrument presets:

1. **Piano**: Bright attack with long decay
2. **Organ**: Sustained sine wave
3. **Flute**: Smooth attack with slight vibrato
4. **Violin**: Long attack with vibrato
5. **Clarinet**: Rich harmonic content from sawtooth
6. **Synth Lead**: Fast attack square wave with filter sweep

## Performance Considerations

- All audio computation uses NumPy for vectorization
- Pre-allocated buffers to minimize garbage collection
- Separate audio thread to prevent GUI blocking
- Efficient phase accumulation to avoid numerical drift
- Anti-aliasing waveforms to prevent aliasing artifacts

## Development Roadmap

- [ ] Additive synthesis
- [ ] Subtractive synthesis
- [ ] FM synthesis
- [ ] Wavetable synthesis
- [ ] Karplus-Strong algorithm
- [ ] Polyphonic MIDI input
- [ ] Plugin system for custom oscillators/filters
- [ ] Audio recording/export

## License

MIT

## Author

Audio Synthesis Team

---

**Note**: This is a prototype/educational synthesizer. For production use, consider additional optimization and safety features.
