import math
from typing import Dict, List, NamedTuple, Optional, Set

from PyQt6.QtCore import QEvent, QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QEventPoint,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QGridLayout, QWidget, QLabel

from gui.scope_widget import ScopeWidget


# --- Geometria della griglia -------------------------------------------------
_RADIUS = 27
_MARGIN_X = 26
_MARGIN_Y = 28
_STEP_X = _RADIUS * 2.15
_STEP_Y = _RADIUS * 1.85

# Raggio di hit-test: leggermente maggiore del raggio dell'esagono, cosi' anche
# gli spazi tra una cella e l'altra (che prima erano "zone morte") suonano la
# cella piu' vicina. Questo e' cio' che rende il touch affidabile col dito.
_HIT_RADIUS_SQ = (_RADIUS * 1.25) ** 2

_MOUSE_ID = -1  # id "pointer" riservato al mouse (i touch hanno id >= 0)

_BG_COLOR = QColor(9, 14, 28)
_IDLE_COLOR = QColor(20, 28, 44)
_FIRST_MIDI_NOTE = 48
_NUM_COLORED_NOTES = 48


class _Cell(NamedTuple):
    """Tutto cio' che serve per disegnare e colpire una cella, precalcolato."""

    midi_note: int
    x: float
    y: float
    path: QPainterPath
    dirty: QRect        # rettangolo da invalidare quando la cella cambia stato
    label_rect: QRect
    name: str
    idle_pen: QPen
    idle_brush: QBrush
    on_pen: QPen
    on_brush: QBrush


class HexGridCanvas(QWidget):
    """Custom widget that draws the hexagonal note matrix."""

    cell_note_on = pyqtSignal(int, float)
    cell_note_off = pyqtSignal(int)

    def __init__(self, note_mapper, parent=None, glide: bool = True):
        super().__init__(parent)
        self.note_mapper = note_mapper
        self.glide = glide  # se True, trascinare il dito/mouse cambia nota
        self.active_notes: Set[int] = set()
        self.note_frequencies: Dict[int, float] = {}

        # pointer_id (mouse = -1, touch = id del punto) -> nota premuta
        self._pointer_notes: Dict[int, int] = {}

        self._cells: List[_Cell] = []
        self._cells_by_note: Dict[int, _Cell] = {}
        self._palette = self._build_palette()
        self._label_font = QFont(self.font())

        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        # Riempiamo sempre tutto lo sfondo nel paintEvent: Qt puo' evitare di
        # cancellarlo prima.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    # ------------------------------------------------------------------ cache
    @staticmethod
    def _build_palette() -> List[QColor]:
        return [
            QColor.fromHsv(
                int(i * 300 / 47), 110 + int(i * 30 / 47), 130 + int(i * 30 / 47)
            )
            for i in range(_NUM_COLORED_NOTES)
        ]

    def _color_for_note(self, midi_note: int) -> QColor:
        index = midi_note - _FIRST_MIDI_NOTE
        if 0 <= index < _NUM_COLORED_NOTES:
            return self._palette[index]
        return _IDLE_COLOR

    @staticmethod
    def _hexagon_points(center_x: float, center_y: float, radius: float):
        points = []
        for index in range(6):
            angle_deg = 60 * index - 30
            x = center_x + radius * math.cos(math.radians(angle_deg))
            y = center_y + radius * math.sin(math.radians(angle_deg))
            points.append((x, y))
        return points

    def rebuild_geometry(self) -> None:
        """Da chiamare solo se cambia il layout del note_mapper."""
        self._cells = []
        self._cells_by_note = {}
        self._ensure_geometry()
        self.update()

    def _ensure_geometry(self) -> None:
        if self._cells:
            return

        rows = self.note_mapper.get_all_mapped_keys()
        for row_index, row in enumerate(reversed(rows)):
            for col_index, key in enumerate(row):
                midi_note = self.note_mapper.key_to_midi(key)
                if midi_note is None:
                    continue

                x = _MARGIN_X + col_index * _STEP_X + (row_index % 2) * (_STEP_X / 2.0)
                y = _MARGIN_Y + row_index * _STEP_Y

                points = self._hexagon_points(x, y, _RADIUS)
                path = QPainterPath()
                path.moveTo(*points[0])
                for point in points[1:]:
                    path.lineTo(*point)
                path.closeSubpath()

                on_color = self._color_for_note(midi_note)
                cell = _Cell(
                    midi_note=midi_note,
                    x=x,
                    y=y,
                    path=path,
                    dirty=path.boundingRect().adjusted(-3, -3, 3, 3).toAlignedRect(),
                    label_rect=QRect(
                        int(x - _RADIUS), int(y - _RADIUS), _RADIUS * 2, _RADIUS * 2
                    ),
                    name=self.note_mapper.get_note_name(midi_note),
                    idle_pen=QPen(_IDLE_COLOR.lighter(120), 1.5, Qt.PenStyle.SolidLine),
                    idle_brush=QBrush(_IDLE_COLOR),
                    on_pen=QPen(on_color.lighter(120), 1.5, Qt.PenStyle.SolidLine),
                    on_brush=QBrush(on_color),
                )
                self._cells.append(cell)
                self._cells_by_note[midi_note] = cell

    # ------------------------------------------------------------- hit testing
    def _cell_at(self, position: QPointF) -> Optional[_Cell]:
        """Cella il cui centro e' piu' vicino al punto (entro il raggio di hit)."""
        self._ensure_geometry()
        px, py = position.x(), position.y()
        best: Optional[_Cell] = None
        best_dist = _HIT_RADIUS_SQ
        for cell in self._cells:
            dx = cell.x - px
            dy = cell.y - py
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best = cell
                best_dist = dist
        return best

    # ------------------------------------------------- stato dei "pointer"
    def _press(self, pointer_id: int, cell: _Cell) -> None:
        if pointer_id in self._pointer_notes:
            self._release(pointer_id)

        midi_note = cell.midi_note
        already_held = midi_note in self._pointer_notes.values()
        self._pointer_notes[pointer_id] = midi_note
        if already_held:
            return  # un altro dito sta gia' suonando questa nota

        frequency = self.note_mapper.midi_to_frequency(midi_note)
        self.active_notes.add(midi_note)
        self.note_frequencies[midi_note] = frequency

        # Luce subito (repaint sincrono ma solo su una cella), poi suono.
        self.repaint(cell.dirty)
        self.cell_note_on.emit(midi_note, frequency)

    def _release(self, pointer_id: int) -> None:
        midi_note = self._pointer_notes.pop(pointer_id, None)
        if midi_note is None:
            return
        if midi_note in self._pointer_notes.values():
            return  # un altro dito la sta ancora tenendo

        self.active_notes.discard(midi_note)
        self.note_frequencies.pop(midi_note, None)

        cell = self._cells_by_note.get(midi_note)
        if cell is not None:
            self.repaint(cell.dirty)
        self.cell_note_off.emit(midi_note)

    def _move(self, pointer_id: int, position: QPointF) -> None:
        if not self.glide or pointer_id not in self._pointer_notes:
            return
        cell = self._cell_at(position)
        if cell is None or cell.midi_note == self._pointer_notes[pointer_id]:
            return
        self._release(pointer_id)
        self._press(pointer_id, cell)

    def release_all(self) -> None:
        for pointer_id in list(self._pointer_notes):
            self._release(pointer_id)

    # ----------------------------------------------------------------- touch
    def event(self, event):
        event_type = event.type()

        if event_type in (
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
            QEvent.Type.TouchEnd,
        ):
            for point in event.points():
                state = point.state()
                pointer_id = point.id()
                if state == QEventPoint.State.Pressed:
                    cell = self._cell_at(point.position())
                    if cell is not None:
                        self._press(pointer_id, cell)
                elif state == QEventPoint.State.Released:
                    self._release(pointer_id)
                elif state == QEventPoint.State.Updated:
                    self._move(pointer_id, point.position())
            event.accept()
            return True

        if event_type == QEvent.Type.TouchCancel:
            for pointer_id in [p for p in self._pointer_notes if p >= 0]:
                self._release(pointer_id)
            event.accept()
            return True

        return super().event(event)

    # ----------------------------------------------------------------- mouse
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._cell_at(event.position())
            if cell is not None:
                self._press(_MOUSE_ID, cell)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if _MOUSE_ID in self._pointer_notes:
            self._move(_MOUSE_ID, event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and _MOUSE_ID in self._pointer_notes:
            self._release(_MOUSE_ID)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def hideEvent(self, event) -> None:
        self.release_all()  # evita note "appese" se la finestra sparisce
        super().hideEvent(event)

    # ---------------------------------------------- chiamate esterne (tastiera)
    def note_on(self, midi_note: int, frequency: float) -> None:
        self.note_frequencies[midi_note] = frequency
        if midi_note in self.active_notes:
            return  # gia' acceso localmente dal tocco: niente repaint inutile
        self.active_notes.add(midi_note)
        self._update_note(midi_note)

    def note_off(self, midi_note: int) -> None:
        self.note_frequencies.pop(midi_note, None)
        if midi_note not in self.active_notes:
            return
        self.active_notes.discard(midi_note)
        self._update_note(midi_note)

    def _update_note(self, midi_note: int) -> None:
        cell = self._cells_by_note.get(midi_note)
        if cell is not None:
            self.update(cell.dirty)
        else:
            self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:
        self._ensure_geometry()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = event.rect()
        painter.fillRect(clip, _BG_COLOR)
        painter.setFont(self._label_font)

        active_notes = self.active_notes
        for cell in self._cells:
            if not clip.intersects(cell.dirty):
                continue  # cella fuori dall'area da ridisegnare

            active = cell.midi_note in active_notes
            painter.setPen(cell.on_pen if active else cell.idle_pen)
            painter.setBrush(cell.on_brush if active else cell.idle_brush)
            painter.drawPath(cell.path)

            if active:
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(cell.label_rect, Qt.AlignmentFlag.AlignCenter, cell.name)


class HexGridWindow(QWidget):
    """A honeycomb note grid with the 4-octave keyboard layout beneath it."""

    cell_note_on = pyqtSignal(int, float)
    cell_note_off = pyqtSignal(int)

    def __init__(self, note_mapper, parent=None):
        super().__init__(parent)
        self.note_mapper = note_mapper
        self.setWindowTitle("Note Hive")
        self.resize(1200, 540)
        self.setMinimumSize(900, 420)
        self.setStyleSheet("background: #0b1020; color: #eaf2ff;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        self.main_layout.addLayout(top_layout, stretch=1)

        self.hex_canvas = HexGridCanvas(self.note_mapper)
        self.hex_canvas.setMinimumHeight(260)
        self.hex_canvas.setMinimumWidth(690)
        self.hex_canvas.cell_note_on.connect(self.cell_note_on)
        self.hex_canvas.cell_note_off.connect(self.cell_note_off)
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
        top_layout.addWidget(scope_group, stretch=2)

        self.keyboard_group = QGroupBox("Keyboard Layout (4 Octaves)")
        self.keyboard_group.setStyleSheet(
            "QGroupBox { border: 1px solid #4c5cff; border-radius: 8px; padding-top: 10px; color: #eaf2ff; }"
        )
        keyboard_layout = QGridLayout(self.keyboard_group)
        keyboard_layout.setHorizontalSpacing(5)
        keyboard_layout.setVerticalSpacing(6)
        keyboard_layout.setColumnMinimumWidth(0, 72)
        self.keyboard_key_labels = []

        layout_info = self.note_mapper.get_all_mapped_keys()
        for row_index, keys in enumerate(layout_info):
            octave_label = QLabel(f"Octave {row_index + 3}")
            octave_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #56e0c2;")
            keyboard_layout.addWidget(octave_label, row_index, 0)

            for column_index, key in enumerate(keys, start=1):
                info = self.note_mapper.get_key_info(key)
                label = QLabel(f"{info['note_name']}\n{info['key'].upper()}")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setMinimumSize(40, 38)
                label.setStyleSheet(
                    "background: #141c2c; border: 1px solid #263653; "
                    "border-radius: 3px; padding: 2px; font-size: 10px; font-weight: bold;"
                )
                keyboard_layout.addWidget(label, row_index, column_index)
                self.keyboard_key_labels.append(label)

        for column_index in range(1, 13):
            keyboard_layout.setColumnStretch(column_index, 1)

        self.main_layout.addWidget(self.keyboard_group)

    def note_on(self, midi_note: int, frequency: float) -> None:
        self.hex_canvas.note_on(midi_note, frequency)

    def note_off(self, midi_note: int) -> None:
        self.hex_canvas.note_off(midi_note)
