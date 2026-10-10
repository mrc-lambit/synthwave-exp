import math
from typing import Dict, Set

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget, QLabel

from gui.scope_widget import ScopeWidget


class HexGridCanvas(QWidget):
    """Custom widget that draws the hexagonal note matrix."""

    def __init__(self, note_mapper, parent=None):
        super().__init__(parent)
        self.note_mapper = note_mapper
        self.active_notes: Set[int] = set()
        self.note_frequencies: Dict[int, float] = {}

    def note_on(self, midi_note: int, frequency: float) -> None:
        self.active_notes.add(midi_note)
        self.note_frequencies[midi_note] = frequency
        self.update()

    def note_off(self, midi_note: int) -> None:
        self.active_notes.discard(midi_note)
        self.note_frequencies.pop(midi_note, None)
        self.update()

    def _get_cell_color(self, midi_note: int) -> QColor:
        colors = [
            QColor.fromHsv(
                int(i * 300 / 47), 110 + int(i * 30 / 47), 130 + int(i * 30 / 47)
            )
            for i in range(48)
        ]
        griglia_4x12 = [colors[i : i + 12] for i in range(0, 48, 12)]

        if midi_note not in self.active_notes:
            return QColor(20, 28, 44)

        midi_index = midi_note - 48
        if 0 <= midi_index < 48:
            row_index, col_index = divmod(midi_index, 12)
            return griglia_4x12[row_index][col_index]

        return QColor(20, 28, 44)

    def _hexagon_points(self, center_x: float, center_y: float, radius: float):
        points = []
        for index in range(6):
            angle_deg = 60 * index - 30
            x = center_x + radius * math.cos(math.radians(angle_deg))
            y = center_y + radius * math.sin(math.radians(angle_deg))
            points.append((x, y))
        return points

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(9, 14, 28))

        rows = self.note_mapper.get_all_mapped_keys()
        margin_x = 26
        margin_y = 28
        radius = 27
        step_x = radius * 2.15
        step_y = radius * 1.85

        for row_index, row in enumerate(reversed(rows)):
            for col_index, key in enumerate(row):
                midi_note = self.note_mapper.key_to_midi(key)
                if midi_note is None:
                    continue

                x = margin_x + col_index * step_x + (row_index % 2) * (step_x / 2.0)
                y = margin_y + row_index * step_y

                points = self._hexagon_points(x, y, radius)
                path = QPainterPath()
                path.moveTo(*points[0])
                for point in points[1:]:
                    path.lineTo(*point)
                path.closeSubpath()

                color = self._get_cell_color(midi_note)
                painter.setPen(QPen(color.lighter(120), 1.5, Qt.PenStyle.SolidLine))
                painter.setBrush(color)
                painter.drawPath(path)

                if midi_note in self.active_notes:
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.drawText(
                        int(x - radius), int(y - radius), int(radius * 2), int(radius * 2),
                        Qt.AlignmentFlag.AlignCenter,
                        self.note_mapper.get_note_name(midi_note),
                    )


class HexGridWindow(QWidget):
    """A honeycomb note grid with the 4-octave keyboard layout beneath it."""

    def __init__(self, note_mapper, parent=None):
        super().__init__(parent)
        self.note_mapper = note_mapper
        self.setWindowTitle("Note Hive")
        self.resize(1100, 540)
        self.setMinimumSize(900, 420)
        self.setStyleSheet("background: #0b1020; color: #eaf2ff;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        self.main_layout.addLayout(top_layout, stretch=1)

        self.hex_canvas = HexGridCanvas(self.note_mapper)
        self.hex_canvas.setMinimumHeight(260)
        top_layout.addWidget(self.hex_canvas, stretch=3)

        scope_group = QGroupBox("Scope & Monitor")
        scope_group.setStyleSheet(
            "QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; color: #eaf2ff; }"
        )
        scope_layout = QVBoxLayout(scope_group)
        self.scope_widget = ScopeWidget()
        scope_layout.addWidget(self.scope_widget, stretch=1)
        self.monitor_label = QLabel("Underruns: 0\nActive Voices: 0")
        self.monitor_label.setStyleSheet("font-family: Consolas; font-size: 10px; color: #eaf2ff;")
        scope_layout.addWidget(self.monitor_label)
        top_layout.addWidget(scope_group, stretch=1)

        self.keyboard_group = QGroupBox("Keyboard Layout (4 Octaves)")
        self.keyboard_group.setStyleSheet(
            "QGroupBox { border: 1px solid #4c5cff; border-radius: 8px; padding-top: 10px; color: #eaf2ff; }"
        )
        keyboard_layout = QVBoxLayout(self.keyboard_group)

        layout_info = self.note_mapper.get_all_mapped_keys()
        labels = ['octave_3', 'octave_4', 'octave_5', 'octave_6']
        row_meta = {
            'octave_3': layout_info[0],
            'octave_4': layout_info[1],
            'octave_5': layout_info[2],
            'octave_6': layout_info[3],
        }

        for row_name in labels:
            row_text = " | ".join(
                f"{self.note_mapper.get_key_info(key)['key'].upper()}: {self.note_mapper.get_key_info(key)['note_name']} ({self.note_mapper.get_key_info(key)['frequency']:.1f} Hz)"
                for key in row_meta[row_name]
            )
            label = QLabel(row_text)
            label.setStyleSheet("font-size: 9px; color: #eaf2ff;")
            keyboard_layout.addWidget(label)

        self.main_layout.addWidget(self.keyboard_group)

    def note_on(self, midi_note: int, frequency: float) -> None:
        self.hex_canvas.note_on(midi_note, frequency)

    def note_off(self, midi_note: int) -> None:
        self.hex_canvas.note_off(midi_note)

