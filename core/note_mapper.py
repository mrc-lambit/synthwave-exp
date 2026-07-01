# -*- coding: utf-8 -*-
"""
Note Mapper module for PC keyboard → MIDI note frequency conversion.

Maps physical QWERTY keyboard keys to musical note frequencies.
Supports 4 playable octaves (C3 to B6, 48 notes total).
"""

from typing import Dict, Optional, Tuple


class NoteMapper:
    """
    Maps PC keyboard keys to MIDI note numbers and frequencies.

    Layout:
    - Octave 3 row: C3 through B3 (12 notes)
    - Octave 4 row: C4 through B4 (12 notes)
    - Octave 5 row: C5 through B5 (12 notes)
    - Octave 6 row: C6 through B6 (12 notes)

    The four rows are available for wider polyphonic input.
    """
    
    # MIDI note constants
    MIDI_C4 = 60  # Lowest note
    MIDI_C5 = 72  # Middle octave start
    MIDI_C6 = 84  # Upper octave start
    
    # A4 reference (440 Hz standard tuning)
    A4_MIDI = 69
    A4_FREQ = 440.0
    
    # Semitone frequency multiplier
    SEMITONE_RATIO = 2.0 ** (1.0 / 12.0)  # ~1.059463
    
    def __init__(self) -> None:
        """Initialize the note mapper with a four-octave QWERTY layout."""
        self._build_keymap()

    def _build_keymap(self) -> None:
        """Build mapping from keyboard keys to MIDI notes."""
        octave_rows = [
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", '\\'],
            ['q', '2', 'w', '3', 'e', 'r', '5', 't', '6', 'y', '7', 'u'],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', '[', ']'],
            ['1', '4', '6', '8', '9', '0', '-', '=', 'p', 'o', 'i', '`'],
        ]

        self._octave_rows = []
        self._key_to_midi: Dict[str, int] = {}

        for octave_index, keys in enumerate(octave_rows):
            base_note = 48 + (octave_index * 12)
            notes = list(range(base_note, base_note + 12))
            self._octave_rows.append(keys)
            for key, note in zip(keys, notes):
                self._key_to_midi[key] = note
    
    def key_to_frequency(self, key: str) -> Optional[float]:
        """
        Convert a keyboard key to its corresponding frequency in Hz.
        
        Args:
            key: Single character key (case-insensitive)
            
        Returns:
            Frequency in Hz, or None if key is not mapped
        """
        key_lower = key.lower()
        
        if key_lower not in self._key_to_midi:
            return None
        
        midi_note = self._key_to_midi[key_lower]
        return self.midi_to_frequency(midi_note)
    
    def key_to_midi(self, key: str) -> Optional[int]:
        """
        Convert a keyboard key to its MIDI note number.
        
        Args:
            key: Single character key (case-insensitive)
            
        Returns:
            MIDI note number (0-127), or None if key is not mapped
        """
        key_lower = key.lower()
        return self._key_to_midi.get(key_lower)
    
    @staticmethod
    def midi_to_frequency(midi_note: int) -> float:
        """
        Convert MIDI note number to frequency in Hz.
        
        Uses standard A4 = 440 Hz tuning.
        Formula: f = 440 * 2^((n-69)/12)
        
        Args:
            midi_note: MIDI note number (0-127)
            
        Returns:
            Frequency in Hz
        """
        semitones_from_a4 = midi_note - 69
        frequency = 440.0 * (NoteMapper.SEMITONE_RATIO ** semitones_from_a4)
        return frequency
    
    @staticmethod
    def frequency_to_midi(frequency: float) -> int:
        """
        Convert frequency in Hz to nearest MIDI note number.
        
        Args:
            frequency: Frequency in Hz
            
        Returns:
            MIDI note number (0-127)
        """
        import math
        semitones_from_a4 = 12 * math.log2(frequency / 440.0)
        midi_note = round(69 + semitones_from_a4)
        return max(0, min(127, midi_note))  # Clamp to valid range
    
    def get_all_mapped_keys(self) -> list[list[str]]:
        """
        Get all mapped key rows.

        Returns:
            List of octave rows, each containing the physical keys for one octave.
        """
        return [row[:] for row in self._octave_rows]
    
    def get_note_name(self, midi_note: int) -> str:
        """
        Get the note name (e.g., "C4", "A#5") for a MIDI note.
        
        Args:
            midi_note: MIDI note number (0-127)
            
        Returns:
            Note name string (e.g., "C4", "C#4")
        """
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_note // 12) - 1
        note = note_names[midi_note % 12]
        return f"{note}{octave}"
    
    def get_key_info(self, key: str) -> Optional[Dict]:
        """
        Get complete information for a keyboard key.
        
        Args:
            key: Keyboard key (case-insensitive)
            
        Returns:
            Dict with 'key', 'midi_note', 'frequency', 'note_name', or None if unmapped
        """
        key_lower = key.lower()
        
        if key_lower not in self._key_to_midi:
            return None
        
        midi_note = self._key_to_midi[key_lower]
        frequency = self.midi_to_frequency(midi_note)
        note_name = self.get_note_name(midi_note)
        
        return {
            'key': key_lower,
            'midi_note': midi_note,
            'frequency': frequency,
            'note_name': note_name
        }


# Module-level instance for convenience
_default_mapper = NoteMapper()


def key_to_frequency(key: str) -> Optional[float]:
    """Convert keyboard key to frequency using default mapper."""
    return _default_mapper.key_to_frequency(key)


def key_to_midi(key: str) -> Optional[int]:
    """Convert keyboard key to MIDI note using default mapper."""
    return _default_mapper.key_to_midi(key)


def midi_to_frequency(midi_note: int) -> float:
    """Convert MIDI note to frequency using default mapper."""
    return NoteMapper.midi_to_frequency(midi_note)
