# -*- coding: utf-8 -*-
"""Chord and harmonic mode handling for the synthesizer."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional


class HarmonicMode(str, Enum):
    """Supported harmonic playing modes."""

    SINGLE = "single"
    DYAD = "dyad"
    TRIAD = "triad"


class ChordType(str, Enum):
    """Supported chord quality definitions."""

    MAJOR = "major"
    MINOR = "minor"
    DIMINISHED = "diminished"
    AUGMENTED = "augmented"
    THIRD_MAJOR = "third-major"
    THIRD_MINOR = "third-minor"
    FOURTH = "fourth"
    FIFTH = "fifth"


class ChordEngine:
    """Generate note collections for different harmonic modes."""

    def __init__(self) -> None:
        self._intervals = {
            HarmonicMode.SINGLE: [0],
            HarmonicMode.DYAD: {
                ChordType.THIRD_MAJOR: [0, 4],
                ChordType.THIRD_MINOR: [0, 3],
                ChordType.FOURTH: [0, 5],
                ChordType.FIFTH: [0, 7],
            },
            HarmonicMode.TRIAD: {
                ChordType.MAJOR: [0, 4, 7],
                ChordType.MINOR: [0, 3, 7],
                ChordType.DIMINISHED: [0, 3, 6],
                ChordType.AUGMENTED: [0, 4, 8],
            },
        }

    def get_notes_for_mode(
        self,
        root_midi: int,
        mode: HarmonicMode,
        chord_type: Optional[ChordType] = None,
    ) -> List[int]:
        """Return the MIDI notes for the requested harmonic mode."""
        if mode == HarmonicMode.SINGLE:
            intervals = [0]
        elif mode == HarmonicMode.DYAD:
            intervals = self._intervals[mode].get(chord_type or ChordType.THIRD_MAJOR, [0, 4])
        elif mode == HarmonicMode.TRIAD:
            intervals = self._intervals[mode].get(chord_type or ChordType.MAJOR, [0, 4, 7])
        else:
            intervals = [0]
        return [root_midi + interval for interval in intervals]
