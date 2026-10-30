import math
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

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
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QComboBox, QPushButton, QVBoxLayout, QGridLayout, QWidget, QLabel

from gui.scope_widget import ScopeWidget

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
        self._pointer_notes: Dict[int, int] = {}

        self._cells: List[_Cell] = []
        self._cells_by_note: Dict[int, List[_Cell]] = {}
        self._palette = self._build_palette()
        self._label_font = QFont(self.font())

        # Parametri geometrici dinamici
        self._radius = 27.0
        self._step_x = 0.0
        self._step_y = 0.0
        self._margin_x = 0.0
        self._margin_y = 0.0
        self._hit_radius_sq = 0.0
        self._layout_mode = "keyboard"  # 'keyboard' | 'tonnetz'

        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)


    @staticmethod
    def _build_palette() -> List[QColor]:
        palette = []
        sat_scale = 0.8

        for i in range(_NUM_COLORED_NOTES):
            midi_note = _FIRST_MIDI_NOTE + i
            pitch_class = midi_note % 12  # 0..11 (C, C#, D, ...)
            octave = ((i // 12)+1)/2              # 0..3 (ottava)

            # Tinta cromaticamente fissa per classe di nota (360° / 12 = 30° a semitono)
            hue = int(pitch_class * 360 / 12)

            # Saturazione e decremento scalati proporzionalmente
            base_sat = 220 * sat_scale
            step_sat = 35 * sat_scale
            saturation = int(max(10, base_sat - (octave * step_sat)))

            # Luminosità invariata per mantenere la leggibilità delle ottave acute
            value = min(255, 70 + (octave * 30))

            palette.append(QColor.fromHsv(hue, saturation, value))
        return palette

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

    # ------------------------------------------------------------- layout
    def set_layout_mode(self, mode: str) -> None:
        """'keyboard' (alveare), 'tonnetz'."""
        if mode in ("keyboard", "tonnetz") and mode != self._layout_mode:
            self._layout_mode = mode
            self.rebuild_geometry()

    def rebuild_geometry(self) -> None:
        self._relayout()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _ensure_geometry(self) -> None:
        if not self._cells:
            self._relayout()

    def _unit_positions(self, aspect: float) -> List[Tuple[int, float, float]]:
        """Centro di ogni nota in unita' di raggio-cella, limitando le ripetizioni."""
        rows = self.note_mapper.get_all_mapped_keys()
        units: List[Tuple[int, float, float]] = []

        if self._layout_mode == "keyboard":
            for row_index, row in enumerate(rows):
                for col_index, key in enumerate(row):
                    midi_note = self.note_mapper.key_to_midi(key)
                    if midi_note is not None:
                        units.append((
                            midi_note,
                            col_index * 2.15 + (row_index % 2) * 1.075,
                            row_index * 1.85,
                        ))
            return units

        notes = sorted({
            m for row in rows for key in row
            for m in [self.note_mapper.key_to_midi(key)] if m is not None
        })
        if not notes:
            return units

        if self._layout_mode == "tonnetz":
            min_note = notes[0]
            max_note = notes[-1]
            
            # Contatore per limitare le ripetizioni a 2 per ogni nota
            note_counts = {m: 0 for m in notes}
            
            # Esploriamo lo spazio partendo dal centro per mantenere il layout compatto
            coords = []
            for q in range(-20, 20):
                for r in range(-20, 20):
                    coords.append((q, r))
            
            # Ordina le coordinate per distanza radiale dal centro (0, 0)
            coords.sort(key=lambda p: p[0]**2 + p[1]**2)

            for q, r in coords:
                m = min_note + 7 * q + 4 * r
                
                # Aggiunge la cella solo se è nel range e non ha ancora superato le 2 copie
                if min_note <= m <= max_note and note_counts.get(m, 0) < 2:
                    x = (r + q // 2 + 0.5 * (q % 2)) * 2.15
                    y = -q * 1.85
                    units.append((m, x, y))
                    note_counts[m] += 1
                    
                    # Interrompe il ciclo se tutte le note hanno raggiunto le 2 ripetizioni
                    if all(c >= 2 for c in note_counts.values()):
                        break

        return units

    def _relayout(self) -> None:
        self._cells = []
        self._cells_by_note = {}
        w, h = float(self.width()), float(self.height())
        if w < 1 or h < 1:
            return
        units = self._unit_positions(w / h)
        if not units:
            return

        xs = [p[1] for p in units]
        ys = [p[2] for p in units]
        bw = max(xs) - min(xs) + 2.0
        bh = max(ys) - min(ys) + 2.0
        radius = max(8.0, min(w / bw, h / bh))
        self._radius = radius
        mid_x = (max(xs) + min(xs)) / 2.0
        mid_y = (max(ys) + min(ys)) / 2.0
        self._label_font.setPixelSize(max(8, int(radius * 0.45)))

        for midi_note, ux, uy in units:
            x = w / 2.0 + (ux - mid_x) * radius
            y = h / 2.0 + (uy - mid_y) * radius

            points = self._hexagon_points(x, y, radius)
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
                label_rect=QRect(int(x - radius), int(y - radius), int(radius * 2), int(radius * 2)),
                name=self.note_mapper.get_note_name(midi_note),
                idle_pen=QPen(_IDLE_COLOR.lighter(240), 1, Qt.PenStyle.SolidLine),
                idle_brush=QBrush(_IDLE_COLOR),
                on_pen=QPen(on_color.lighter(240), 1, Qt.PenStyle.SolidLine),
                on_brush=QBrush(on_color),
            )
            self._cells.append(cell)
            
            # Raggruppiamo tutte le repliche della stessa nota
            if midi_note not in self._cells_by_note:
                self._cells_by_note[midi_note] = []
            self._cells_by_note[midi_note].append(cell)

        # Raggio di hit: ottimizzato per griglie enormi calcolando solo un campione
        check_limit = min(30, len(self._cells))
        nearest = min(
            (math.hypot(a.x - b.x, a.y - b.y)
             for i, a in enumerate(self._cells[:check_limit]) 
             for b in self._cells[i + 1:]),
            default=2.15 * radius,
        )
        self._hit_radius_sq = max(1.25 * radius, 0.6 * nearest) ** 2

    def _cell_at(self, position: QPointF) -> Optional[_Cell]:
        """Cella il cui centro e' piu' vicino al punto (entro il raggio di hit)."""
        self._ensure_geometry()
        px, py = position.x(), position.y()
        best: Optional[_Cell] = None
        best_dist = self._hit_radius_sq
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

        # Aggiorna graficamente tutte le copie (ripetizioni) della nota toccata
        self._update_note(midi_note)
        self.cell_note_on.emit(midi_note, frequency)

    def _release(self, pointer_id: int) -> None:
        midi_note = self._pointer_notes.pop(pointer_id, None)
        if midi_note is None:
            return
        if midi_note in self._pointer_notes.values():
            return  # un altro dito la sta ancora tenendo

        # La luce NON si spegne qui: MainWindow conta le sorgenti per nota
        # (touch, tastiera PC, MIDI) e chiama note_off() solo quando l'ultima
        # viene rilasciata. Spegnere localmente la farebbe sparire mentre una
        # nota MIDI e' ancora tenuta. L'emit e' sincrono, quindi lo spegnimento
        # avviene comunque subito.
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
            alive = set()
            for point in event.points():
                state = point.state()
                pointer_id = point.id()
                if state != QEventPoint.State.Released:
                    alive.add(pointer_id)
                if state == QEventPoint.State.Pressed:
                    cell = self._cell_at(point.position())
                    if cell is not None:
                        self._press(pointer_id, cell)
                elif state == QEventPoint.State.Released:
                    self._release(pointer_id)
                elif state == QEventPoint.State.Updated:
                    self._move(pointer_id, point.position())

            # Riconciliazione anti-"nota appesa": Qt elenca in ogni evento tutti i punti attivi. 
            # Un dito che avevamo registrato ma che non c'e' piu'
            # (Release perso/accorpato con tocchi molto rapidi) viene rilasciato.
            for pointer_id in [p for p in self._pointer_notes if p >= 0 and p not in alive]:
                self._release(pointer_id)
            if event_type == QEvent.Type.TouchEnd:
                for pointer_id in [p for p in self._pointer_notes if p >= 0]:
                    self._release(pointer_id)  # nessun dito rimasto
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
        cells = self._cells_by_note.get(midi_note)
        if cells:
            for cell in cells:
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
        self.setStyleSheet("background: #0b1020; color: #eaf2ff;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        # Pulsanti Toggle
        btn_layout = QHBoxLayout()

        self.toggle_kb_btn = QPushButton("Keyboard")
        self.toggle_kb_btn.setStyleSheet(
            "QPushButton { background: #1f2d48; border: 1px solid #4c5cff; border-radius: 4px; padding: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #2a3c60; }"
        )
        self.toggle_kb_btn.clicked.connect(self._show_keyboard)
        btn_layout.addWidget(self.toggle_kb_btn)

        self.toggle_scope_btn = QPushButton("Scope Monitors")
        self.toggle_scope_btn.setStyleSheet(
            "QPushButton { background: #1f2d48; border: 1px solid #4c5cff; border-radius: 4px; padding: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #2a3c60; }"
        )
        self.toggle_scope_btn.clicked.connect(self._show_scope)
        btn_layout.addWidget(self.toggle_scope_btn)

        self.layout_combo = QComboBox()
        for label, mode in (("Alveare", "keyboard"), ("Tonnetz", "tonnetz")):
            self.layout_combo.addItem(label, mode)
        self.layout_combo.setStyleSheet(
            "QComboBox { background: #1f2d48; border: 1px solid #4c5cff; border-radius: 4px; "
            "padding: 4px; font-weight: bold; }"
            "QComboBox QAbstractItemView { background: #1f2d48; color: #eaf2ff; }"
        )
        self.layout_combo.currentIndexChanged.connect(
            lambda _i: self.hex_canvas.set_layout_mode(self.layout_combo.currentData())
        )
        btn_layout.addWidget(self.layout_combo)

        self.main_layout.addLayout(btn_layout)

        # Hex Canvas in alto (prende tutto lo spazio verticale disponibile se i pannelli sotto sono nascosti)
        self.hex_canvas = HexGridCanvas(self.note_mapper)
        self.hex_canvas.cell_note_on.connect(self.cell_note_on)
        self.hex_canvas.cell_note_off.connect(self.cell_note_off)
        self.main_layout.addWidget(self.hex_canvas, stretch=1)

        # Contenitore inferiore per Scope o Keyboard
        # Scope Group
        self.scope_group = QGroupBox("Scope Graphs")
        self.scope_group.setStyleSheet(
            "QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; color: #eaf2ff; }"
        )
        scope_layout = QVBoxLayout(self.scope_group)
        self.scope_widget = ScopeWidget()
        scope_layout.addWidget(self.scope_widget, stretch=1)
        self.monitor_label = QLabel("Underruns: 0\nActive Voices: 0")
        self.monitor_label.setStyleSheet("font-family: Consolas; font-size: 10px; color: #eaf2ff;")
        scope_layout.addWidget(self.monitor_label)
        self.main_layout.addWidget(self.scope_group)
        self.scope_group.hide()

        # Keyboard Group
        self.keyboard_group = QGroupBox("Keyboard Notes (4 Octaves)")
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
        self.keyboard_group.hide()

    def _show_keyboard(self) -> None:
        """Mostra la tastiera e nasconde lo scope. Se è già visibile, la nasconde."""
        was_visible = self.keyboard_group.isVisible()
        self.scope_group.hide()
        self.keyboard_group.setVisible(not was_visible)

    def _show_scope(self) -> None:
        """Mostra lo scope e nasconde la tastiera. Se è già visibile, lo nasconde."""
        was_visible = self.scope_group.isVisible()
        self.keyboard_group.hide()
        self.scope_group.setVisible(not was_visible)

    def note_on(self, midi_note: int, frequency: float) -> None:
        self.hex_canvas.note_on(midi_note, frequency)

    def note_off(self, midi_note: int) -> None:
        self.hex_canvas.note_off(midi_note)