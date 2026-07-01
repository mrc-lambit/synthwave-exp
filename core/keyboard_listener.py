# -*- coding: utf-8 -*-
"""
Keyboard Listener module for real-time QWERTY keyboard input handling.

Integrates with PyQt6 event system to detect key press/release and
route them to the AudioEngine for note on/off events.
"""

from typing import Optional, Callable, Dict
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QKeyEvent

from core.note_mapper import NoteMapper


class KeyboardListener(QObject):
    """
    Listens to keyboard events and converts them to note on/off signals.
    
    Emits signals when:
    - A mapped key is pressed (note_on signal)
    - A mapped key is released (note_off signal)
    
    Prevents key repeat events from triggering multiple note_on calls.
    """
    
    # PyQt6 signals
    note_on = pyqtSignal(int, float)  # (midi_note, frequency)
    note_off = pyqtSignal(int)  # (midi_note)
    
    def __init__(self) -> None:
        """Initialize the keyboard listener."""
        super().__init__()
        
        self.note_mapper = NoteMapper()
        
        # Track currently pressed keys to prevent repeated note_on from key repeat
        self.pressed_keys: Dict[str, int] = {}  # {key: midi_note}
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        Handle keyboard press event.
        
        Args:
            event: QKeyEvent from Qt
            
        Returns:
            True if event was handled (consumed), False otherwise
        """
        # Ignore key repeat events (only process first press)
        if event.isAutoRepeat():
            return False
        
        key = event.text().lower()
        
        # Check if this key is mapped to a note
        midi_note = self.note_mapper.key_to_midi(key)
        if midi_note is None:
            return False
        
        # Only trigger note_on if key is not already pressed
        if key in self.pressed_keys:
            return True  # Key already pressed, consume event
        
        # Record that this key is now pressed
        self.pressed_keys[key] = midi_note
        
        # Get frequency and emit signal
        frequency = self.note_mapper.midi_to_frequency(midi_note)
        self.note_on.emit(midi_note, frequency)
        
        return True  # Event handled
    
    def handle_key_release(self, event: QKeyEvent) -> bool:
        """
        Handle keyboard release event.
        
        Args:
            event: QKeyEvent from Qt
            
        Returns:
            True if event was handled (consumed), False otherwise
        """
        # Ignore auto-repeat events
        if event.isAutoRepeat():
            return False
        
        key = event.text().lower()
        
        # Check if this key is currently tracked as pressed
        if key not in self.pressed_keys:
            return False
        
        # Get the MIDI note for this key
        midi_note = self.pressed_keys[key]
        
        # Remove from pressed keys
        del self.pressed_keys[key]
        
        # Emit note_off signal
        self.note_off.emit(midi_note)
        
        return True  # Event handled
    
    def get_pressed_notes(self) -> list:
        """
        Get list of currently pressed MIDI notes.
        
        Returns:
            List of MIDI note numbers currently pressed
        """
        return list(set(self.pressed_keys.values()))
    
    def release_all_notes(self) -> None:
        """
        Release all currently pressed notes (e.g., on window focus loss).
        """
        keys_to_release = list(self.pressed_keys.keys())
        for key in keys_to_release:
            midi_note = self.pressed_keys[key]
            del self.pressed_keys[key]
            self.note_off.emit(midi_note)
    
    def get_key_layout(self) -> Dict[str, list[Dict]]:
        """
        Get the complete keyboard layout with note info.

        Returns:
            Dict keyed by row labels with the mapped key information for each octave row.
        """
        rows = self.note_mapper.get_all_mapped_keys()

        layout: Dict[str, list[Dict]] = {
            'octave_3': [],
            'octave_4': [],
            'octave_5': [],
            'octave_6': [],
        }

        for index, row in enumerate(rows):
            label = list(layout.keys())[index]
            for key in row:
                info = self.note_mapper.get_key_info(key)
                if info:
                    layout[label].append(info)

        return layout
