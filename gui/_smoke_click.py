# -*- coding: utf-8 -*-
"""Offscreen smoke test: clicking a hex cell emits note_on/note_off with the right MIDI note."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "venv", "Lib", "site-packages"))

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication

from core.note_mapper import NoteMapper
from gui.hex_grid_window import HexGridCanvas

app = QApplication([])
mapper = NoteMapper()
canvas = HexGridCanvas(mapper)
canvas.resize(800, 300)

received_on = []
received_off = []
canvas.cell_note_on.connect(lambda note, freq: received_on.append((note, round(freq, 2))))
canvas.cell_note_off.connect(lambda note: received_off.append(note))


def click(x, y):
    pos = QPointF(x, y)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress, pos,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease, pos,
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press)
    canvas.mouseReleaseEvent(release)


# First cell drawn: row_index=0, col_index=0 -> center (26, 28).
# Layout is reversed rows, so row 0 is octave 6 (MIDI 84..95): cell (0,0) -> MIDI 84.
click(26.0, 28.0)
# Click in an empty area (bottom-right corner) should emit nothing.
click(795.0, 295.0)

print("note_on events:", received_on)
print("note_off events:", received_off)
assert received_on == [(84, round(mapper.midi_to_frequency(84), 2))], "press failed"
assert received_off == [84], "release failed"
assert canvas._pressed_note is None, "stuck pressed note"
print("SMOKE_TEST_OK")
