# -*- coding: utf-8 -*-
"""
Note Mapper module for PC keyboard → MIDI note frequency conversion.

Maps physical QWERTY keyboard keys to musical note frequencies.
Supports 2 simultaneously active octaves (C4 to G6, 24 notes total).
"""

from typing import Dict, Optional, Tuple


class NoteMapper:
    """
    Maps PC keyboard keys to MIDI note numbers and frequencies.
    
    Layout:
    - Upper row (Z-]): C5 through G6 (12 notes)
    - Lower row (Q-]): C4 through G5 (12 notes)
    
    Both rows are active simultaneously for 2-octave polyphonic input.
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
        """Initialize the note mapper with QWERTY keyboard layout."""
        self._build_keymap()
    
    def _build_keymap(self) -> None:
        """Build mapping from keyboard keys to MIDI notes."""
        # Upper row: z s x d c v g b h n j m
        # Notes: C5 D5 E5 F5 G5 A5 B5 C6 D6 E6 F6 G6
        upper_keys = ['z', 's', 'x', 'd', 'c', 'v', 'g', 'b', 'h', 'n', 'j', 'm']
        upper_notes = list(range(72, 84))  # MIDI 72-83 (C5-B5)
        
        # Lower row: q 2 w 3 e r 5 t 6 y 7 u
        # Notes: C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5
        lower_keys = ['q', '2', 'w', '3', 'e', 'r', '5', 't', '6', 'y', '7', 'u']
        lower_notes = list(range(60, 72))  # MIDI 60-71 (C4-B4)
        
        # Build the key-to-MIDI-note mapping
        self._key_to_midi: Dict[str, int] = {}
        
        for key, note in zip(upper_keys, upper_notes):
            self._key_to_midi[key] = note
        
        for key, note in zip(lower_keys, lower_notes):
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
    
    def get_all_mapped_keys(self) -> tuple:
        """
        Get all mapped keys.
        
        Returns:
            Tuple of (upper_row_keys, lower_row_keys) as lists of strings
        """
        upper_row = ['z', 's', 'x', 'd', 'c', 'v', 'g', 'b', 'h', 'n', 'j', 'm']
        lower_row = ['q', '2', 'w', '3', 'e', 'r', '5', 't', '6', 'y', '7', 'u']
        return (upper_row, lower_row)
    
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
