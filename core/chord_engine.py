# -*- coding: utf-8 -*-
"""Chord and harmonic mode handling for the synthesizer."""

from __future__ import annotations

from enum import Enum
from typing import List


class HarmonicMode(str, Enum):
    """Supported harmonic playing modes."""

    SINGLE = "single"
    DYAD = "dyad"
    TRIAD = "triad"


class ChordEngine:
    """Generate note collections for different harmonic modes."""

    def __init__(self) -> None:
        self._intervals = {
            HarmonicMode.SINGLE: [0],
            HarmonicMode.DYAD: [0, 4],
            HarmonicMode.TRIAD: [0, 4, 7],
        }

    def get_notes_for_mode(self, root_midi: int, mode: HarmonicMode) -> List[int]:
        """Return the MIDI notes for the requested harmonic mode."""
        intervals = self._intervals.get(mode, [0])
        return [root_midi + interval for interval in intervals]
