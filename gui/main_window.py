"""
Main Window module for the MUSA synthesizer GUI.

Provides the primary user interface with:
- Audio engine controls (Start/Stop)
- Master volume slider
- Oscillator type selector
- Keyboard display/layout info
"""

import sys
import wave
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QDial, QComboBox, QLabel,
    QGroupBox, QGridLayout, QFileDialog, QSpinBox, QLineEdit,
    QSizePolicy, QTabWidget, QScrollArea
)

from PyQt6.QtCore import Qt, QTimer, QEvent, pyqtSlot
from PyQt6.QtGui import QKeyEvent

from audio.engine import AudioEngine
from core.note_mapper import NoteMapper
from core.chord_engine import ChordEngine, ChordType, HarmonicMode
from core.keyboard_listener import KeyboardListener
from core.midi_input import MidiInput
from core.preset_manager import PresetManager
from gui.hex_grid_window import HexGridWindow


_MAIN_WINDOW_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #111827;
    color: #e5e7eb;
    font-family: "Segoe UI";
}
QLabel {
    background: transparent;
}
QDial {
    background: transparent;
}
QGroupBox {
    background-color: #182230;
    border: 1px solid #2b3a4d;
    border-radius: 8px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #b6c4d6;
    font-weight: 600;
}
QPushButton {
    background-color: #222f43;
    color: #94a3b8;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #d1d5db;
    color: #1e293b;
    }
QPushButton:pressed, QPushButton:checked {
    background-color: #dddddd;
    color: #1e293b;
}
QPushButton:disabled {
    background-color: #334155;
    color: #94a3b8;
}
QComboBox, QSpinBox, QLineEdit {
    background-color: #0f1724;
    color: #e5e7eb;
    border: 1px solid #344256;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #2563eb;
}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #3b82f6;
}
QComboBox QAbstractItemView {
    background-color: #182230;
    color: #e5e7eb;
    border: 1px solid #344256;
    selection-background-color: #2563eb;
}
QTabWidget::pane {
    background-color: #182230;
    border: 1px solid #2b3a4d;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #0f1724;
    color: #aebdd0;
    border: 1px solid #2b3a4d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 12px;
    margin-right: 3px;
}
QTabBar::tab:selected {
    background-color: #182230;
    color: #ffffff;
    border-color: #344256;
}
QTabBar::tab:hover:!selected {
    background-color: #243247;
}
QScrollArea {
    background-color: #111827;
    border: none;
}
QScrollBar:vertical {
    background-color: #111827;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #344256;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4b607a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QStatusBar {
    background-color: #0f1724;
    color: #aebdd0;
    border-top: 1px solid #2b3a4d;
}
QToolTip {
    background-color: #182230;
    color: #e5e7eb;
    border: 1px solid #344256;
    padding: 4px;
}
"""

class MainWindow(QMainWindow):
    """
    Main window for the Muse synth.
    
    Manages:
    - Audio engine lifecycle
    - Keyboard input routing
    - GUI controls and display
    - Real-time status updates
    """
    
    def __init__(self) -> None:
        """Initialize the main window and audio engine."""
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)

        super().__init__()
        
        self.setWindowTitle("Muse SynthWave")
        self.setGeometry(100, 40, 1000, 500)
        self.setStyleSheet(_MAIN_WINDOW_STYLESHEET)
        
        # Audio engine
        self.audio_engine: AudioEngine = AudioEngine()

        self.attack_time = 0.01
        self.decay_time = 0.1
        self.sustain_level = 0.7
        self.release_time = 0.3
        
        # Keyboard listener
        self.keyboard_listener: KeyboardListener = KeyboardListener()
        self.midi_input = MidiInput()
        self.note_mapper: NoteMapper = NoteMapper()
        self.chord_engine: ChordEngine = ChordEngine()
        self.preset_manager: PresetManager = PresetManager()
        self.harmonic_mode: HarmonicMode = HarmonicMode.SINGLE
        self.chord_type: ChordType = ChordType.MAJOR
        
        # Track all generated voices for each pressed key so chord tones stop together
        self.midi_note_voices: dict[int, list[int]] = {}
        self.external_midi_voices: dict[tuple[int, int], list[list[int]]] = {}
        self.active_note_sources: dict[int, int] = {}
        self.midi_pitch_bend_factors: dict[int, float] = {}
        self.midi_channel_pressure: dict[int, int] = {}
        self.midi_poly_pressure: dict[tuple[int, int], int] = {}
        self.midi_voice_base_amplitudes: dict[int, float] = {}
        
        # Connect keyboard signals to audio engine
        self._connect_keyboard_signals()

        self.hex_window = HexGridWindow(self.note_mapper)
        self.scope_widget = self.hex_window.scope_widget
        self.monitor_label = self.hex_window.monitor_label
        self.hex_window.cell_note_on.connect(self._on_note_on)
        self.hex_window.cell_note_off.connect(self._on_note_off)
        self.hex_window.hide()

        # Setup UI
        self._setup_ui()
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(100)  # Update every 100ms
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_audio_monitor)
        self.monitor_timer.start(100)
        
        # Engine state
        self.is_running = False
        self._app.installEventFilter(self)
    
    def _setup_ui(self) -> None:
        """Setup the main user interface."""
        # Keep the controls accessible when the window is shorter than their natural layout size.
        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)

        # Central widget
        central_widget = QWidget()
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        central_widget.setLayout(main_layout)
        
        main_grid = QGridLayout()
        main_grid.setHorizontalSpacing(10)
        main_grid.setVerticalSpacing(8)
        for column in range(3):
            main_grid.setColumnStretch(column, 1)
        main_layout.addLayout(main_grid)

        control_group = self._create_control_panel()
        self.synthesis_group = self._create_synthesis_panel()
        controls_column = QWidget()
        controls_column_layout = QVBoxLayout(controls_column)
        controls_column_layout.setContentsMargins(0, 0, 0, 0)
        controls_column_layout.setSpacing(8)
        controls_column_layout.addWidget(control_group)
        controls_column_layout.addWidget(self.synthesis_group)
        main_grid.addWidget(controls_column, 0, 0, 1, 2)

        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(8)

        self.preset_group, self.sample_group = self._create_sampler_panels()
        right_column_layout.addWidget(self.preset_group)
        right_column_layout.addWidget(self.sample_group)

        lfo_group = self._create_lfo_panel()
        right_column_layout.addWidget(lfo_group)
        main_grid.addWidget(right_column, 0, 2)

        self.adsr_group = self._create_adsr_panel()
        main_grid.addWidget(self.adsr_group, 1, 0)

        self.filter_group = self._create_filter_panel()
        main_grid.addWidget(self.filter_group, 1, 1)

        effect_groups = self._create_master_effect_panels()
        main_grid.addWidget(effect_groups["distortion"], 1, 2)
        main_grid.addWidget(effect_groups["delay"], 2, 0)
        main_grid.addWidget(effect_groups["chorus"], 2, 1)
        main_grid.addWidget(effect_groups["reverb"], 2, 2)

        self.statusBar().showMessage("Ready")
        self._show_startup_banner()
        self.main_scroll_area.setWidget(central_widget)
        self.setCentralWidget(self.main_scroll_area)
    
    def _show_startup_banner(self) -> None:
        """Show a short startup banner in the status bar."""
        self.statusBar().showMessage("MUSA Synth ready — press Start Audio to begin")
        self.hex_window.show()

    def _create_keyboard_display(self) -> QGroupBox:
        """Create keyboard layout display for four playable octaves."""
        group = QGroupBox("Keyboard Layout (4 Octaves)")
        layout = QVBoxLayout()

        layout_info = self.keyboard_listener.get_key_layout()
        labels = ['octave_3', 'octave_4', 'octave_5', 'octave_6']

        for row_name in labels:
            row_label = QLabel()
            layout.addWidget(row_label)

            row_text = " | ".join(
                f"{info['key'].upper()}: {info['note_name']} ({info['frequency']:.1f} Hz)"
                for info in layout_info[row_name]
            )
            row_display = QLabel(row_text)
            row_display.setStyleSheet("font-size: 9px;")
            layout.addWidget(row_display)

        group.setLayout(layout)
        return group

    @staticmethod
    def _configure_selector(selector: QComboBox) -> None:
        selector.setFixedSize(160, 30)
        selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        selector.setMinimumContentsLength(8)

    @staticmethod
    def _configure_button(button: QPushButton) -> None:
        button.setFixedSize(120, 30)

    @staticmethod
    def _configure_dial(dial: QDial) -> None:
        dial.setNotchesVisible(True)
        dial.setNotchTarget(((dial.maximum() - dial.minimum()) // 5))

    @staticmethod
    def _add_labeled_selector(
        layout: QGridLayout,
        row: int,
        label_text: str,
        selector: QComboBox,
    ) -> None:
        layout.addWidget(QLabel(label_text), row, 0)
        layout.addWidget(selector, row, 1)
        layout.setColumnMinimumWidth(0, 70)



    def _create_control_panel(self) -> QGroupBox:
        """Create compact Audio and MIDI control tabs."""
        group = QGroupBox("Audio Controls")
        layout = QVBoxLayout()
        self.control_tabs = QTabWidget()
        layout.addWidget(self.control_tabs)

        audio_page = QWidget()
        audio_layout = QHBoxLayout(audio_page)
        audio_controls = QVBoxLayout()

        command_row = QHBoxLayout()
        self.start_stop_btn = QPushButton("Start Audio")
        self._configure_button(self.start_stop_btn)
        self.start_stop_btn.setCheckable(True)
        self.start_stop_btn.clicked.connect(self._on_start_stop_clicked)
        command_row.addWidget(self.start_stop_btn)

        self.record_btn = QPushButton("Record")
        self._configure_button(self.record_btn)
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._on_record_clicked)
        command_row.addWidget(self.record_btn)
        audio_controls.addLayout(command_row)

        volume_col = QVBoxLayout()
        volume_col.addWidget(QLabel("Volume"), alignment=Qt.AlignmentFlag.AlignHCenter)
        self.volume_slider = QDial()
        self.volume_slider.setRange(0, 100)
        self._configure_dial(self.volume_slider)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedSize(42, 42)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_col.addWidget(self.volume_slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.volume_label = QLabel("0.80")
        volume_col.addWidget(self.volume_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        audio_controls.addLayout(volume_col)

        selector_column = QGridLayout()
        selector_column.setVerticalSpacing(6)
        selector_column.addWidget(QLabel("Mode:"), 1, 0)
        self.mode_selector = QComboBox()
        self._configure_selector(self.mode_selector)
        self.mode_selector.addItems([mode.value for mode in HarmonicMode])
        self.mode_selector.currentTextChanged.connect(self._on_mode_changed)
        selector_column.addWidget(self.mode_selector, 1, 1)

        selector_column.addWidget(QLabel("Chord:"), 2, 0)
        self.chord_selector = QComboBox()
        self._configure_selector(self.chord_selector)
        self.chord_selector.addItems([chord.value for chord in ChordType])
        self.chord_selector.currentTextChanged.connect(self._on_chord_type_changed)
        selector_column.addWidget(self.chord_selector, 2, 1)

        selector_column.setColumnMinimumWidth(0, 85)
        audio_layout.addLayout(audio_controls, 1)
        audio_layout.addLayout(selector_column, 2)
        self.control_tabs.addTab(audio_page, "Audio")

        engine_page = QWidget()
        engine_layout = QVBoxLayout(engine_page)

        midi_selector_row = QHBoxLayout()
        midi_selector_row.addWidget(QLabel("MIDI Input:"))
        self.midi_input_selector = QComboBox()
        self.midi_input_selector.setMinimumContentsLength(12)
        self.midi_input_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.midi_input_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.midi_input_selector.addItem("MIDI: Off", None)
        self.midi_input_selector.currentIndexChanged.connect(self._on_midi_port_changed)
        midi_selector_row.addWidget(self.midi_input_selector, 7)
        midi_selector_row.addStretch(3)
        refresh_midi_btn = QPushButton("Refresh")
        self._configure_button(refresh_midi_btn)
        refresh_midi_btn.clicked.connect(self._refresh_midi_ports)
        midi_selector_row.addWidget(refresh_midi_btn)
        engine_layout.addLayout(midi_selector_row)

        buffer_size_row = QHBoxLayout()
        buffer_size_row.addWidget(QLabel("Buffer size:"))
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(64, 512)
        self.buffer_size.setSingleStep(64)
        self.buffer_size.setSuffix(" samples")
        self.buffer_size.setKeyboardTracking(False)
        self.buffer_size.setValue(self.audio_engine.buffer_size)
        self.buffer_size.valueChanged.connect(self._on_buffer_size_changed)
        buffer_size_row.addWidget(self.buffer_size)
        buffer_size_row.addStretch(1)
        engine_layout.addLayout(buffer_size_row)

        sample_rate_row = QHBoxLayout()
        sample_rate_row.addWidget(QLabel("Sample rate:"))
        self.sample_rate_selector = QComboBox()
        self._configure_selector(self.sample_rate_selector)
        for sample_rate in (22050, 44100, 48000, 88200, 96000):
            self.sample_rate_selector.addItem(f"{sample_rate} Hz", sample_rate)
        sample_rate_index = self.sample_rate_selector.findData(
            self.audio_engine.sample_rate
        )
        if sample_rate_index < 0:
            self.sample_rate_selector.addItem(
                f"{self.audio_engine.sample_rate} Hz",
                self.audio_engine.sample_rate,
            )
            sample_rate_index = self.sample_rate_selector.count() - 1
        self.sample_rate_selector.setCurrentIndex(sample_rate_index)
        self.sample_rate_selector.currentIndexChanged.connect(
            self._on_sample_rate_changed
        )
        sample_rate_row.addWidget(self.sample_rate_selector)
        sample_rate_row.addStretch(1)
        engine_layout.addLayout(sample_rate_row)
        engine_layout.addStretch(1)
        self._refresh_midi_ports()

        self.control_tabs.addTab(engine_page, "MIDI / Engine")

        group.setLayout(layout)
        return group

    def _create_sampler_panels(self) -> tuple[QGroupBox, QGroupBox]:
        """Create preset and sample panels for the main window sidebar."""
        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout(preset_group)
        self._add_preset_controls(preset_layout)

        sample_group = QGroupBox("Sample")
        sample_layout = QVBoxLayout(sample_group)
        sample_load_row = QHBoxLayout()
        self.sample_button = QPushButton("Load WAV")
        self._configure_button(self.sample_button)
        self.sample_button.clicked.connect(self._on_load_sample)
        sample_load_row.addWidget(self.sample_button)
        self.remove_sample_button = QPushButton("Remove WAV")
        self._configure_button(self.remove_sample_button)
        self.remove_sample_button.setEnabled(False)
        self.remove_sample_button.clicked.connect(self._on_remove_sample)
        sample_load_row.addWidget(self.remove_sample_button)
        sample_layout.addLayout(sample_load_row)

        self.sample_label = QLabel("No sample loaded")
        self.sample_label.setWordWrap(True)
        sample_layout.addWidget(self.sample_label)

        sample_root_row = QHBoxLayout()
        sample_root_row.addWidget(QLabel("Sample root MIDI:"))
        self.sample_root_note = QSpinBox()
        self.sample_root_note.setRange(0, 127)
        self.sample_root_note.setValue(69)
        self.sample_root_note.valueChanged.connect(self._on_sample_root_changed)
        sample_root_row.addWidget(self.sample_root_note)
        sample_root_row.addStretch(1)
        sample_layout.addLayout(sample_root_row)

        return preset_group, sample_group

    def _create_synthesis_panel(self) -> QGroupBox:
        """Create visible synthesis and Unison controls outside the tabs."""
        group = QGroupBox("Synthesis Engine")
        layout = QGridLayout(group)

        layout.addWidget(QLabel("Engine:"), 0, 0)
        self.synthesis_mode_selector = QComboBox()
        self._configure_selector(self.synthesis_mode_selector)
        self.synthesis_mode_selector.addItems(["waveform", "additive", "fm"])
        self.synthesis_mode_selector.currentTextChanged.connect(
            self._on_synthesis_mode_changed
        )
        layout.addWidget(self.synthesis_mode_selector, 0, 1)

        layout.addWidget(QLabel("Waveform:"), 0, 2)
        self.oscillator_selector = QComboBox()
        self._configure_selector(self.oscillator_selector)
        self.oscillator_selector.addItems(["sine", "square", "triangle", "sawtooth"])
        self.oscillator_selector.currentTextChanged.connect(self._on_oscillator_changed)
        layout.addWidget(self.oscillator_selector, 0, 3)

        self.unison_voices = QDial()
        self.unison_voices.setRange(1, 7)
        self._configure_dial(self.unison_voices)
        self.unison_voices.setFixedSize(42, 42)
        self.unison_voices.setValue(1)
        self.unison_voices.valueChanged.connect(self._on_unison_changed)

        self.detune_cents = QDial()
        self.detune_cents.setRange(0, 50)
        self._configure_dial(self.detune_cents)
        self.detune_cents.setFixedSize(42, 42)
        self.detune_cents.setValue(0)
        self.detune_cents.valueChanged.connect(self._on_unison_changed)

        self.additive_partials = QDial()
        self.additive_partials.setRange(1, 16)
        self._configure_dial(self.additive_partials)
        self.additive_partials.setFixedSize(42, 42)
        self.additive_partials.setValue(8)
        self.additive_partials.valueChanged.connect(
            self._on_synthesis_parameters_changed
        )

        self.additive_tilt = QDial()
        self.additive_tilt.setRange(0, 240)
        self._configure_dial(self.additive_tilt)
        self.additive_tilt.setFixedSize(42, 42)
        self.additive_tilt.setValue(60)
        self.additive_tilt.valueChanged.connect(
            self._on_synthesis_parameters_changed
        )

        self.fm_ratio = QDial()
        self.fm_ratio.setRange(5, 80)
        self._configure_dial(self.fm_ratio)
        self.fm_ratio.setFixedSize(42, 42)
        self.fm_ratio.setValue(20)
        self.fm_ratio.valueChanged.connect(self._on_synthesis_parameters_changed)

        self.fm_index = QDial()
        self.fm_index.setRange(0, 120)
        self._configure_dial(self.fm_index)
        self.fm_index.setFixedSize(42, 42)
        self.fm_index.setValue(20)
        self.fm_index.valueChanged.connect(self._on_synthesis_parameters_changed)

        dial_controls = (
            ("Unison", self.unison_voices, str),
            ("Detune (cents)", self.detune_cents, str),
            ("Partials", self.additive_partials, str),
            ("Tilt (dB/oct)", self.additive_tilt, lambda value: f"{value / 10:.1f}"),
            ("FM ratio", self.fm_ratio, lambda value: f"{value / 10:.1f}"),
            ("FM index", self.fm_index, lambda value: f"{value / 10:.1f}"),
        )
        dial_layout = QGridLayout()
        dial_layout.setHorizontalSpacing(4)
        dial_layout.setVerticalSpacing(4)
        for index, (title, dial, format_value) in enumerate(dial_controls):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 2, 0, 2)
            cell_layout.setSpacing(2)
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setWordWrap(True)
            title_label.setFixedHeight(30)
            value_label = QLabel(format_value(dial.value()))
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dial.valueChanged.connect(
                lambda value, label=value_label, formatter=format_value:
                    label.setText(formatter(value))
            )
            cell_layout.addWidget(title_label)
            cell_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(value_label)
            dial_layout.addWidget(cell, 0, index)
            dial_layout.setColumnStretch(index, 1)
        layout.addLayout(dial_layout, 1, 0, 1, 4)
        return group

    def _create_lfo_panel(self) -> QGroupBox:
        """Create LFO modulation controls."""
        group = QGroupBox("LFO")
        layout = QGridLayout()

        self.lfo_target_selector = QComboBox()
        self._configure_selector(self.lfo_target_selector)
        self.lfo_target_selector.addItems(["pitch", "volume", "filter"])
        self.lfo_target_selector.currentTextChanged.connect(self._on_lfo_target_changed)
        self._add_labeled_selector(layout, 0, "Target:", self.lfo_target_selector)

        self.lfo_rate_slider = QDial()
        self.lfo_rate_slider.setRange(0, 50)
        self._configure_dial(self.lfo_rate_slider)
        self.lfo_rate_slider.setFixedSize(42, 42)
        self.lfo_rate_slider.valueChanged.connect(self._on_lfo_changed)

        self.lfo_depth_slider = QDial()
        self.lfo_depth_slider.setRange(0, 100)
        self._configure_dial(self.lfo_depth_slider)
        self.lfo_depth_slider.setFixedSize(42, 42)
        self.lfo_depth_slider.valueChanged.connect(self._on_lfo_changed)

        layout.addWidget(QLabel("Rate (Hz)"), 1, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Depth (%)"), 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lfo_rate_slider, 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lfo_depth_slider, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lfo_rate_label = QLabel("Rate: 0.0")
        self.lfo_depth_label = QLabel("0")
        self.lfo_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lfo_depth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lfo_rate_label, 3, 0)
        layout.addWidget(self.lfo_depth_label, 3, 1)
        layout.setColumnMinimumWidth(0, 70)

        group.setLayout(layout)
        return group



    def _create_adsr_panel(self) -> QGroupBox:
        """Create ADSR parameter controls."""
        group = QGroupBox("ADSR")
        layout = QGridLayout()

        labels = ["Attack", "Decay", "Sustain", "Release"]
        defaults = [0.01, 0.1, 0.7, 0.3]
        self.adsr_sliders = {}
        self.adsr_value_labels = {}

        for index, (label, default_value) in enumerate(zip(labels, defaults)):
            slider = QDial()
            slider.setRange(1, 200)
            self._configure_dial(slider)
            slider.setValue(int(default_value * 100))
            slider.setFixedSize(42, 42)
            slider.valueChanged.connect(lambda value, name=label.lower(): self._on_adsr_changed(name, value / 100.0))
            layout.addWidget(QLabel(label), 0, index, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(slider, 1, index, alignment=Qt.AlignmentFlag.AlignCenter)
            value_label = QLabel(f"{default_value:.2f}")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(value_label, 2, index)
            slider.valueChanged.connect(lambda value, output=value_label: output.setText(f"{value / 100.0:.2f}"))
            self.adsr_sliders[label.lower()] = slider
            self.adsr_value_labels[label.lower()] = value_label

        group.setLayout(layout)
        return group

    def _create_filter_panel(self) -> QGroupBox:
        """Create filter controls."""
        group = QGroupBox("Filter")

        layout = QGridLayout()

        self.filter_selector = QComboBox()
        self._configure_selector(self.filter_selector)
        self.filter_selector.addItems(["lowpass", "highpass", "bandpass"])
        self.filter_selector.currentTextChanged.connect(self._on_filter_changed)

        self._add_labeled_selector(layout, 0, "Type:", self.filter_selector)

        self.cutoff_slider = QDial()
        self.cutoff_slider.setRange(50, 20000)
        self._configure_dial(self.cutoff_slider)
        self.cutoff_slider.setValue(2000)
        self.cutoff_slider.setFixedSize(42, 42)
        self.cutoff_slider.valueChanged.connect(lambda value: self._on_filter_changed(self.filter_selector.currentText(), value))
        cutoff_label = QLabel("Cutoff (Hz)")
        cutoff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(cutoff_label, 1, 0)
        layout.addWidget(self.cutoff_slider, 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.cutoff_value_label = QLabel("2000")
        self.cutoff_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cutoff_value_label, 3, 0)
        self.cutoff_slider.valueChanged.connect(lambda value: self.cutoff_value_label.setText(str(value)))

        self.resonance_slider = QDial()
        self.resonance_slider.setRange(0, 100)
        self._configure_dial(self.resonance_slider)
        self.resonance_slider.setValue(0)
        self.resonance_slider.setFixedSize(42, 42)
        self.resonance_slider.valueChanged.connect(lambda value: self._on_filter_changed(self.filter_selector.currentText(), self.cutoff_slider.value(), value / 100.0))    
        resonance_label = QLabel("Resonance (%)")
        resonance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(resonance_label, 1, 1)
        layout.addWidget(self.resonance_slider, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.resonance_value_label = QLabel("0")
        self.resonance_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.resonance_value_label, 3, 1)
        self.resonance_slider.valueChanged.connect(lambda value: self.resonance_value_label.setText(str(value)))

        group.setLayout(layout)
        return group

    @staticmethod
    def _add_master_dial(layout, column: int, label: str, dial: QDial, value_label: QLabel) -> None:
        dial.setFixedSize(42, 42)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(label)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title, 0, column)
        layout.addWidget(dial, 1, column, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label, 2, column)

    def _create_master_effect_panels(self) -> dict[str, QGroupBox]:
        """Create separate effect panels with responsive selectors."""
        groups = {}

        self.distortion_selector = QComboBox()
        self._configure_selector(self.distortion_selector)
        for label, effect in [
            ("Off", "off"),
            ("Soft Clip", "soft_clip"),
            ("Overdrive", "overdrive"),
            ("Hard Clip", "hard_clip"),
            ("Fuzz", "fuzz"),
            ("Bitcrusher", "bitcrush"),
        ]:
            self.distortion_selector.addItem(label, effect)

        self.delay_enabled_selector = QComboBox()
        self._configure_selector(self.delay_enabled_selector)
        self.delay_enabled_selector.addItem("Off", False)
        self.delay_enabled_selector.addItem("On", True)
        self.chorus_enabled_selector = QComboBox()
        self._configure_selector(self.chorus_enabled_selector)
        self.chorus_enabled_selector.addItem("Off", False)
        self.chorus_enabled_selector.addItem("On", True)
        self.reverb_enabled_selector = QComboBox()
        self._configure_selector(self.reverb_enabled_selector)
        self.reverb_enabled_selector.addItem("Off", False)
        self.reverb_enabled_selector.addItem("On", True)

        self.distortion_drive_slider = QDial()
        self.distortion_drive_slider.setRange(0, 100)
        self._configure_dial(self.distortion_drive_slider)
        self.distortion_drive_slider.setValue(0)
        self.distortion_drive_label = QLabel("0")

        self.distortion_mix_slider = QDial()
        self.distortion_mix_slider.setRange(0, 100)
        self._configure_dial(self.distortion_mix_slider)
        self.distortion_mix_slider.setValue(100)
        self.distortion_mix_label = QLabel("100")

        self.delay_time_slider = QDial()
        self.delay_time_slider.setRange(1, 2000)
        self._configure_dial(self.delay_time_slider)
        self.delay_time_slider.setValue(250)
        self.delay_time_label = QLabel("250")

        self.delay_feedback_slider = QDial()
        self.delay_feedback_slider.setRange(0, 95)
        self._configure_dial(self.delay_feedback_slider)
        self.delay_feedback_slider.setValue(30)
        self.delay_feedback_label = QLabel("30")

        self.delay_mix_slider = QDial()
        self.delay_mix_slider.setRange(0, 100)
        self._configure_dial(self.delay_mix_slider)
        self.delay_mix_slider.setValue(25)
        self.delay_mix_label = QLabel("25")

        self.chorus_rate_slider = QDial()
        self.chorus_rate_slider.setRange(1, 50)
        self._configure_dial(self.chorus_rate_slider)
        self.chorus_rate_slider.setValue(8)
        self.chorus_rate_label = QLabel("0.8")

        self.chorus_depth_slider = QDial()
        self.chorus_depth_slider.setRange(0, 100)
        self._configure_dial(self.chorus_depth_slider)
        self.chorus_depth_slider.setValue(60)
        self.chorus_depth_label = QLabel("6.0")

        self.chorus_mix_slider = QDial()
        self.chorus_mix_slider.setRange(0, 100)
        self._configure_dial(self.chorus_mix_slider)
        self.chorus_mix_slider.setValue(25)
        self.chorus_mix_label = QLabel("25")

        self.reverb_decay_slider = QDial()
        self.reverb_decay_slider.setRange(3, 50)
        self._configure_dial(self.reverb_decay_slider)
        self.reverb_decay_slider.setValue(18)
        self.reverb_decay_label = QLabel("1.8")

        self.reverb_mix_slider = QDial()
        self.reverb_mix_slider.setRange(0, 100)
        self._configure_dial(self.reverb_mix_slider)
        self.reverb_mix_slider.setValue(30)
        self.reverb_mix_label = QLabel("30")

        def add_effect_tab(title, selector_label, selector, controls):
            group = QGroupBox(title)
            page_layout = QGridLayout(group)
            self._add_labeled_selector(
                page_layout, 0, selector_label, selector
            )

            dial_layout = QGridLayout()
            dial_layout.setHorizontalSpacing(14)
            dial_layout.setVerticalSpacing(2)
            for column, (label, dial, value_label) in enumerate(controls):
                self._add_master_dial(dial_layout, column, label, dial, value_label)
                dial_layout.setColumnStretch(column, 1)
            page_layout.addLayout(dial_layout, 1, 0, 1, 2)
            page_layout.setRowStretch(2, 1)
            groups[title.lower()] = group

        add_effect_tab(
            "Distortion",
            "Type:",
            self.distortion_selector,
            [
                ("Drive (%)", self.distortion_drive_slider, self.distortion_drive_label),
                ("Mix (%)", self.distortion_mix_slider, self.distortion_mix_label),
            ],
        )
        add_effect_tab(
            "Delay",
            "Effect:",
            self.delay_enabled_selector,
            [
                ("Time (ms)", self.delay_time_slider, self.delay_time_label),
                ("Feedback (%)", self.delay_feedback_slider, self.delay_feedback_label),
                ("Mix (%)", self.delay_mix_slider, self.delay_mix_label),
            ],
        )
        add_effect_tab(
            "Chorus",
            "Effect:",
            self.chorus_enabled_selector,
            [
                ("Rate (Hz)", self.chorus_rate_slider, self.chorus_rate_label),
                ("Depth (ms)", self.chorus_depth_slider, self.chorus_depth_label),
                ("Mix (%)", self.chorus_mix_slider, self.chorus_mix_label),
            ],
        )
        add_effect_tab(
            "Reverb",
            "Effect:",
            self.reverb_enabled_selector,
            [
                ("Decay (s)", self.reverb_decay_slider, self.reverb_decay_label),
                ("Mix (%)", self.reverb_mix_slider, self.reverb_mix_label),
            ],
        )

        self.distortion_selector.currentIndexChanged.connect(self._on_distortion_changed)
        self.distortion_drive_slider.valueChanged.connect(self._on_distortion_changed)
        self.distortion_mix_slider.valueChanged.connect(self._on_distortion_changed)
        self.delay_enabled_selector.currentIndexChanged.connect(self._on_delay_changed)
        self.delay_time_slider.valueChanged.connect(self._on_delay_changed)
        self.delay_feedback_slider.valueChanged.connect(self._on_delay_changed)
        self.delay_mix_slider.valueChanged.connect(self._on_delay_changed)
        self.chorus_enabled_selector.currentIndexChanged.connect(self._on_chorus_changed)
        self.chorus_rate_slider.valueChanged.connect(self._on_chorus_changed)
        self.chorus_depth_slider.valueChanged.connect(self._on_chorus_changed)
        self.chorus_mix_slider.valueChanged.connect(self._on_chorus_changed)
        self.reverb_enabled_selector.currentIndexChanged.connect(self._on_reverb_changed)
        self.reverb_decay_slider.valueChanged.connect(self._on_reverb_changed)
        self.reverb_mix_slider.valueChanged.connect(self._on_reverb_changed)
        self._on_distortion_changed()
        self._on_delay_changed()
        self._on_chorus_changed()
        self._on_reverb_changed()

        self.master_effect_groups = groups
        return groups



    def _add_preset_controls(self, layout: QVBoxLayout) -> None:
        """Add preset selection and actions to the preset panel."""

        self.preset_name_input = QComboBox()
        self.preset_name_input.setEditable(True)
        self.preset_name_input.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.preset_name_input.setMinimumContentsLength(8)
        self.preset_name_input.setMinimumWidth(0)
        self.preset_name_input.setFixedHeight(30)
        self.preset_name_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.preset_name_input.addItems(self.preset_manager.get_available_presets())
        layout.addWidget(self.preset_name_input)
        preset_actions = QHBoxLayout()
        save_btn = QPushButton("Save Preset")
        self._configure_button(save_btn)
        save_btn.clicked.connect(self._on_save_preset)
        preset_actions.addWidget(save_btn)

        load_btn = QPushButton("Load Preset")
        self._configure_button(load_btn)
        load_btn.clicked.connect(self._on_load_preset)
        preset_actions.addWidget(load_btn)
        preset_actions.addStretch(1)
        layout.addLayout(preset_actions)



    def _connect_keyboard_signals(self) -> None:
        """Connect keyboard listener signals to audio engine."""
        self.keyboard_listener.note_on.connect(self._on_note_on)
        self.keyboard_listener.note_off.connect(self._on_note_off)
        self.midi_input.note_on.connect(self._on_midi_note_on)
        self.midi_input.note_off.connect(self._on_midi_note_off)
        self.midi_input.control_change.connect(self._on_midi_control_change)
        self.midi_input.pitch_bend.connect(self._on_midi_pitch_bend)
        self.midi_input.channel_pressure.connect(self._on_midi_channel_pressure)
        self.midi_input.poly_pressure.connect(self._on_midi_poly_pressure)

    def _refresh_midi_ports(self) -> None:
        """Refresh available MIDI input ports without changing selection."""
        selected_port = self.midi_input_selector.currentData() if hasattr(self, "midi_input_selector") else None
        try:
            ports = self.midi_input.input_ports()
        except Exception as error:
            ports = []
            self.statusBar().showMessage(f"MIDI unavailable: {error}")
        if selected_port is not None and selected_port not in ports:
            self._release_midi_notes()
            self.midi_input.close()
            selected_port = None

        self.midi_input_selector.blockSignals(True)
        self.midi_input_selector.clear()
        self.midi_input_selector.addItem("MIDI: Off", None)
        for port in ports:
            self.midi_input_selector.addItem(port, port)
        selected_index = self.midi_input_selector.findData(selected_port)
        self.midi_input_selector.setCurrentIndex(max(0, selected_index))
        self.midi_input_selector.blockSignals(False)

    @pyqtSlot(int)
    def _on_midi_port_changed(self, index: int) -> None:
        """Switch MIDI input and release notes from the old port."""
        self._release_midi_notes()
        self.midi_input.close()
        port_name = self.midi_input_selector.itemData(index)
        if port_name is None:
            self.statusBar().showMessage("MIDI input off")
            return
        try:
            self.midi_input.open_port(port_name)
            self.statusBar().showMessage(f"MIDI input: {port_name}")
        except Exception as error:
            self.statusBar().showMessage(f"Cannot open MIDI input: {error}")
            self.midi_input_selector.blockSignals(True)
            self.midi_input_selector.setCurrentIndex(0)
            self.midi_input_selector.blockSignals(False)

    def _show_active_note(self, midi_note: int, frequency: float) -> None:
        source_count = self.active_note_sources.get(midi_note, 0)
        self.active_note_sources[midi_note] = source_count + 1
        if source_count == 0:
            self.hex_window.note_on(midi_note, frequency)

    def _hide_active_note(self, midi_note: int) -> None:
        source_count = self.active_note_sources.get(midi_note, 0)
        if source_count <= 1:
            self.active_note_sources.pop(midi_note, None)
            self.hex_window.note_off(midi_note)
        else:
            self.active_note_sources[midi_note] = source_count - 1

    def _start_note_voices(self, midi_note: int, amplitude: float) -> list[int]:
        if not self.is_running:
            return []
        notes = self.chord_engine.get_notes_for_mode(
            midi_note,
            self.harmonic_mode,
            self.chord_type,
        )
        mixer = getattr(self.audio_engine, "mixer", None)
        pooled_voices = getattr(mixer, "voices", [])
        sample_loaded = bool(
            pooled_voices and getattr(pooled_voices[0], "sample", None) is not None
        )
        oscillator_type = (
            "sample" if sample_loaded else self.oscillator_selector.currentText()
        )
        voice_ids = []
        for note in notes:
            note_frequency = self.note_mapper.midi_to_frequency(note)
            voice_id = self.audio_engine.note_on(
                note_frequency,
                amplitude,
                oscillator_type,
            )
            if voice_id is not None:
                voice_ids.append(voice_id)
        return voice_ids

    def _release_midi_notes(self) -> None:
        for (channel, midi_note), held_voices in self.external_midi_voices.items():
            for voice_ids in held_voices:
                for voice_id in voice_ids:
                    self.audio_engine.note_off(voice_id)
                    self.midi_voice_base_amplitudes.pop(id(voice_id), None)
                self._hide_active_note(midi_note)
        self.external_midi_voices.clear()
        self.midi_pitch_bend_factors.clear()
        self.midi_channel_pressure.clear()
        self.midi_poly_pressure.clear()

    @pyqtSlot(int, int, int)
    def _on_midi_note_on(self, channel: int, midi_note: int, velocity: int) -> None:
        """Start a note received from the active MIDI controller."""
        frequency = self.note_mapper.midi_to_frequency(midi_note)
        self._show_active_note(midi_note, frequency)
        voice_ids = self._start_note_voices(midi_note, velocity / 127.0)
        bend_factor = self.midi_pitch_bend_factors.get(channel, 1.0)
        for voice_id in voice_ids:
            self.midi_voice_base_amplitudes[id(voice_id)] = getattr(
                voice_id, "amplitude", velocity / 127.0
            )
            voice_frequency = getattr(voice_id, "frequency", None)
            if voice_frequency is not None and bend_factor != 1.0:
                self.audio_engine.set_voice_frequency(
                    voice_id, voice_frequency * bend_factor
                )
        self.external_midi_voices.setdefault((channel, midi_note), []).append(voice_ids)
        self._apply_midi_aftertouch(channel, midi_note)

    @pyqtSlot(int, int)
    def _on_midi_note_off(self, channel: int, midi_note: int) -> None:
        """Release one held note received from MIDI."""
        held_voices = self.external_midi_voices.get((channel, midi_note))
        if not held_voices:
            return
        for voice_id in held_voices.pop(0):
            self.audio_engine.note_off(voice_id)
            self.midi_voice_base_amplitudes.pop(id(voice_id), None)
        self._hide_active_note(midi_note)
        if not held_voices:
            self.external_midi_voices.pop((channel, midi_note), None)
            self.midi_poly_pressure.pop((channel, midi_note), None)

    @pyqtSlot(int, int, int)
    def _on_midi_control_change(self, channel: int, control: int, value: int) -> None:
        """Map common MIDI CCs to master volume, LFO depth, and filter cutoff."""
        normalized_value = max(0, min(127, value)) / 127.0
        if control == 1:
            depth = round(normalized_value * 100)
            self.lfo_depth_slider.setValue(depth)
        elif control == 7:
            volume = round(normalized_value * 100)
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(volume)
            self.volume_slider.blockSignals(False)
            self.volume_label.setText(f"{normalized_value:.2f}")
            self.audio_engine.set_master_volume(normalized_value)
        elif control == 74:
            cutoff = round(50.0 * (400.0 ** normalized_value))
            self.cutoff_slider.setValue(cutoff)

    @pyqtSlot(int, int)
    def _on_midi_pitch_bend(self, channel: int, pitch: int) -> None:
        """Apply the standard +/-2 semitone bend to active notes on a channel."""
        normalized_pitch = max(-8192, min(8191, pitch)) / 8192.0
        bend_factor = 2.0 ** ((normalized_pitch * 2.0) / 12.0)
        previous_factor = self.midi_pitch_bend_factors.get(channel, 1.0)
        ratio = bend_factor / previous_factor
        for (voice_channel, _), held_voices in self.external_midi_voices.items():
            if voice_channel != channel:
                continue
            for voice_ids in held_voices:
                for voice_id in voice_ids:
                    voice_frequency = getattr(voice_id, "frequency", None)
                    if voice_frequency is not None:
                        self.audio_engine.set_voice_frequency(
                            voice_id, voice_frequency * ratio
                        )
        self.midi_pitch_bend_factors[channel] = bend_factor

    @staticmethod
    def _midi_pressure_gain(pressure: int) -> float:
        return 0.25 + 0.75 * max(0, min(127, pressure)) / 127.0

    def _apply_midi_aftertouch(self, channel: int, midi_note: Optional[int] = None) -> None:
        """Apply channel and poly pressure to held MIDI voices only."""
        channel_pressure = self.midi_channel_pressure.get(channel)
        has_poly_pressure = any(
            pressure_channel == channel
            and (midi_note is None or pressure_note == midi_note)
            for pressure_channel, pressure_note in self.midi_poly_pressure
        )
        if channel_pressure is None and not has_poly_pressure:
            return
        channel_gain = (
            self._midi_pressure_gain(channel_pressure)
            if channel_pressure is not None
            else 1.0
        )
        for (voice_channel, voice_note), held_voices in self.external_midi_voices.items():
            if voice_channel != channel or (midi_note is not None and voice_note != midi_note):
                continue
            poly_pressure = self.midi_poly_pressure.get((channel, voice_note))
            poly_gain = (
                self._midi_pressure_gain(poly_pressure)
                if poly_pressure is not None
                else 1.0
            )
            for voice_ids in held_voices:
                for voice_id in voice_ids:
                    base_amplitude = self.midi_voice_base_amplitudes.get(
                        id(voice_id), getattr(voice_id, "amplitude", 0.0)
                    )
                    self.audio_engine.set_voice_amplitude(
                        voice_id, base_amplitude * channel_gain * poly_gain
                    )

    @pyqtSlot(int, int)
    def _on_midi_channel_pressure(self, channel: int, pressure: int) -> None:
        self.midi_channel_pressure[channel] = pressure
        self._apply_midi_aftertouch(channel)

    @pyqtSlot(int, int, int)
    def _on_midi_poly_pressure(self, channel: int, midi_note: int, pressure: int) -> None:
        self.midi_poly_pressure[(channel, midi_note)] = pressure
        self._apply_midi_aftertouch(channel, midi_note)

    @pyqtSlot(int, float)
    def _on_note_on(self, midi_note: int, frequency: float) -> None:
        """Handle note on event from keyboard."""
        self._show_active_note(midi_note, frequency)
        active_voice_ids = self._start_note_voices(midi_note, 0.5)
        if active_voice_ids:
            self.midi_note_voices[midi_note] = active_voice_ids
    
    @pyqtSlot(int)
    def _on_note_off(self, midi_note: int) -> None:
        """Handle note off event from keyboard."""
        self._hide_active_note(midi_note)
        voice_ids = self.midi_note_voices.pop(midi_note, [])
        for voice_id in voice_ids:
            self.audio_engine.note_off(voice_id)
    
    @pyqtSlot()
    def _on_start_stop_clicked(self) -> None:
        """Handle start/stop button click."""
        if self.is_running:
            self._stop_audio()
        else:
            self._start_audio()
    
    @pyqtSlot()
    def _on_record_clicked(self) -> None:
        """Toggle recording of the current audio output."""
        if self.record_btn.isChecked():
            output_path = f"recordings/demo_{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
            try:
                self.audio_engine.start_recording(output_path)
            except Exception as error:
                self.record_btn.setChecked(False)
                self.record_btn.setText("Record")
                self.statusBar().showMessage(
                    f"Error starting recording: {error}"
                )
                return
            self.record_btn.setText("Stop Recording")
            self.statusBar().showMessage("Recording...")
        else:
            recording_error = self.audio_engine.stop_recording()
            self.record_btn.setText("Record")
            message = (
                f"Recording error: {recording_error}"
                if recording_error is not None
                else "Recording stopped"
            )
            self.statusBar().showMessage(message)

    def _start_audio(self) -> None:
        """Start the audio engine."""
        try:
            self.audio_engine.start()
            if not self.audio_engine.is_running:
                raise RuntimeError("Audio stream did not start")
            self.is_running = True
            self.buffer_size.setEnabled(False)
            self.sample_rate_selector.setEnabled(False)
            self.start_stop_btn.setText("Stop Audio")
            self.start_stop_btn.setChecked(True)
            self.statusBar().showMessage("Audio running ▶")
        except Exception as e:
            self.is_running = False
            self.buffer_size.setEnabled(True)
            self.sample_rate_selector.setEnabled(True)
            self.start_stop_btn.setText("Start Audio")
            self.start_stop_btn.setChecked(False)
            self.statusBar().showMessage(f"Error starting audio: {str(e)}")
    
    def _stop_audio(self) -> None:
        """Stop the audio engine and recording safely."""
        recording_error = None
        if self.record_btn.isChecked():
            recording_error = self.audio_engine.stop_recording()
            self.record_btn.setChecked(False)
            self.record_btn.setText("Record")
        self.keyboard_listener.release_all_notes()
        self._release_midi_notes()
        self.audio_engine.stop()
        self.midi_note_voices.clear()
        self.is_running = False
        self.buffer_size.setEnabled(True)
        self.sample_rate_selector.setEnabled(True)
        self.start_stop_btn.setText("Start Audio")
        self.start_stop_btn.setChecked(False)
        status = "Idle | Audio stopped ⏹"
        if recording_error is not None:
            status += f" | Recording error: {recording_error}"
        self.statusBar().showMessage(status)

    def _shutdown_resources(self) -> None:
        """Stop audio, recording, timers, and pending notes during shutdown."""
        self.midi_input.close()
        if self.status_timer.isActive():
            self.status_timer.stop()
        if self.monitor_timer.isActive():
            self.monitor_timer.stop()

        if self.is_running:
            self._stop_audio()
        else:
            self.keyboard_listener.release_all_notes()
            self._release_midi_notes()
            self.audio_engine.stop_recording()

        self.keyboard_listener.release_all_notes()
        self.midi_note_voices.clear()
        self.audio_engine.stop()
        self.audio_engine.stop_recording()
    
    @pyqtSlot(int)
    def _on_volume_changed(self, value: int) -> None:
        """Handle volume slider change."""
        volume = value / 100.0
        self.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{volume:.2f}")

    @pyqtSlot(str)
    def _on_oscillator_changed(self, oscillator_type: str) -> None:
        """Update the selected waveform for active oscillator voices."""
        self.audio_engine.set_oscillator_type(oscillator_type)

    def _on_synthesis_mode_changed(self, mode: str) -> None:
        """Switch synthesis engines without interrupting active notes."""
        self.audio_engine.set_synthesis_mode(mode)

    def _on_synthesis_parameters_changed(self, _value) -> None:
        """Apply additive and FM parameters to the audio engine immediately."""
        self.audio_engine.set_synthesis_parameters(
            additive_partials=self.additive_partials.value(),
            additive_tilt_db_per_octave=self.additive_tilt.value() / 10.0,
            fm_ratio=self.fm_ratio.value() / 10.0,
            fm_index=self.fm_index.value() / 10.0,
        )

    def _on_unison_changed(self, _value: int) -> None:
        """Apply the current Unison controls to the audio engine."""
        self.audio_engine.set_unison_parameters(
            self.unison_voices.value(),
            self.detune_cents.value(),
        )
    
    def _on_load_sample(self) -> None:
        """Choose a WAV sample and use MIDI A4 as its default root note."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load WAV sample", "", "WAV audio (*.wav)"
        )
        if not path:
            return
        try:
            root_frequency = self.note_mapper.midi_to_frequency(self.sample_root_note.value())
            self.audio_engine.load_sample(path, root_frequency)
        except (OSError, ValueError, wave.Error) as error:
            self.statusBar().showMessage(f"Could not load sample: {error}")
            return
        self._set_sample_loaded_ui(Path(path).name)
        self.statusBar().showMessage("WAV sample loaded")

    def _set_sample_loaded_ui(self, sample_name: Optional[str]) -> None:
        loaded = sample_name is not None
        self.sample_label.setText(sample_name or "No sample loaded")
        self.remove_sample_button.setEnabled(loaded)
        self.oscillator_selector.setEnabled(not loaded)

    def _on_remove_sample(self) -> None:
        """Unload the WAV from memory without deleting the source file."""
        self.audio_engine.clear_sample()
        self._set_sample_loaded_ui(None)
        self.statusBar().showMessage("WAV sample removed; oscillator selected")

    def _on_sample_root_changed(self, midi_note: int) -> None:
        self.audio_engine.set_sample_root_frequency(
            self.note_mapper.midi_to_frequency(midi_note)
        )

    def _on_buffer_size_changed(self, size: int) -> None:
        self.audio_engine.set_buffer_size(size)

    def _on_sample_rate_changed(self, _index: int) -> None:
        sample_rate = int(self.sample_rate_selector.currentData())
        try:
            self.audio_engine.set_sample_rate(sample_rate)
        except (OSError, RuntimeError, ValueError) as error:
            current_index = self.sample_rate_selector.findData(
                self.audio_engine.sample_rate
            )
            self.sample_rate_selector.blockSignals(True)
            self.sample_rate_selector.setCurrentIndex(current_index)
            self.sample_rate_selector.blockSignals(False)
            self.statusBar().showMessage(f"Unable to change sample rate: {error}")

    @pyqtSlot(str)
    def _on_mode_changed(self, mode_name: str) -> None:
        """Handle harmonic mode changes."""
        try:
            self.harmonic_mode = HarmonicMode(mode_name)
        except ValueError:
            self.harmonic_mode = HarmonicMode.SINGLE

        if self.harmonic_mode == HarmonicMode.SINGLE:
            self.chord_selector.setEnabled(False)
        else:
            self.chord_selector.setEnabled(True)


    @pyqtSlot(str)
    def _on_chord_type_changed(self, chord_name: str) -> None:
        """Handle chord quality changes."""
        try:
            self.chord_type = ChordType(chord_name)
        except ValueError:
            self.chord_type = ChordType.MAJOR


    @pyqtSlot(str, float)
    def _on_adsr_changed(self, parameter: str, value: float) -> None:
        """Handle ADSR slider changes."""
        if parameter == "attack":
            self.attack_time = value
        elif parameter == "decay":
            self.decay_time = value
        elif parameter == "sustain":
            self.sustain_level = value
        elif parameter == "release":
            self.release_time = value

        self.audio_engine.set_adsr_parameters(
            attack_time=self.attack_time,
            decay_time=self.decay_time,
            sustain_level=self.sustain_level,
            release_time=self.release_time,
        )

    @pyqtSlot(str)
    def _on_filter_changed(self, filter_type: str, cutoff: Optional[int] = None, resonance: Optional[float] = None) -> None:
        """Handle filter parameter changes."""
        if cutoff is None:
            cutoff = self.cutoff_slider.value()
        if resonance is None:
            resonance = self.resonance_slider.value() / 100.0

        self.audio_engine.set_filter(
            kind=filter_type,
            cutoff=float(cutoff),
            resonance=float(resonance),
        )

    @pyqtSlot(str)
    def _on_lfo_target_changed(self, target: str) -> None:
        """Handle LFO target selection."""
        self.audio_engine.set_lfo_parameters(
            frequency=self.lfo_rate_slider.value() / 10.0,
            depth=self.lfo_depth_slider.value() / 100.0,
            target=target,
        )

    def _on_lfo_changed(self, _value: int = 0) -> None:
        """Handle LFO rate/depth changes."""
        rate = self.lfo_rate_slider.value()
        depth = self.lfo_depth_slider.value()
        frequency = rate / 10.0
        self.lfo_rate_label.setText(f"Rate: {frequency:.1f}")
        self.lfo_depth_label.setText(f"Depth: {depth}")
        self.audio_engine.set_lfo_parameters(
            frequency=frequency,
            depth=float(depth) / 100.0,
            target=self.lfo_target_selector.currentText(),
        )

    def _on_distortion_changed(self, _value: int = 0) -> None:
        """Apply master distortion settings immediately."""
        drive = self.distortion_drive_slider.value()
        mix = self.distortion_mix_slider.value()
        self.distortion_drive_label.setText(f"{drive}")
        self.distortion_mix_label.setText(f"{mix}")
        self.audio_engine.set_distortion(
            self.distortion_selector.currentData(), drive / 100.0, mix / 100.0
        )

    def _on_delay_changed(self, _value: int = 0) -> None:
        """Apply master delay settings immediately."""
        time_ms = self.delay_time_slider.value()
        feedback = self.delay_feedback_slider.value()
        mix = self.delay_mix_slider.value()
        self.delay_time_label.setText(str(time_ms))
        self.delay_feedback_label.setText(f"{feedback}")
        self.delay_mix_label.setText(f"{mix}")
        self.audio_engine.set_delay(
            self.delay_enabled_selector.currentData(),
            time_ms,
            feedback / 100.0,
            mix / 100.0,
        )

    def _on_chorus_changed(self, _value: int = 0) -> None:
        """Apply master chorus settings immediately."""
        rate_hz = self.chorus_rate_slider.value() / 10.0
        depth_ms = self.chorus_depth_slider.value() / 10.0
        mix = self.chorus_mix_slider.value()
        self.chorus_rate_label.setText(f"{rate_hz:.1f}")
        self.chorus_depth_label.setText(f"{depth_ms:.1f}")
        self.chorus_mix_label.setText(f"{mix}")
        self.audio_engine.set_chorus(
            self.chorus_enabled_selector.currentData(),
            rate_hz,
            depth_ms,
            mix / 100.0,
        )

    def _on_reverb_changed(self, _value: int = 0) -> None:
        """Apply master reverb settings immediately."""
        decay_seconds = self.reverb_decay_slider.value() / 10.0
        mix = self.reverb_mix_slider.value()
        self.reverb_decay_label.setText(f"{decay_seconds:.1f}")
        self.reverb_mix_label.setText(f"{mix}")
        self.audio_engine.set_reverb(
            self.reverb_enabled_selector.currentData(),
            decay_seconds,
            mix / 100.0,
        )
    
    def _collect_preset_state(self) -> dict:
        """Collect the current synth state into a JSON-serializable dict."""
        return {
            'name': self.preset_name_input.currentText(),
            'waveform': self.oscillator_selector.currentText(),
            'synthesis': {
                'mode': self.synthesis_mode_selector.currentText(),
                'additive_partials': self.additive_partials.value(),
                'additive_tilt_db_per_octave': self.additive_tilt.value() / 10.0,
                'fm_ratio': self.fm_ratio.value() / 10.0,
                'fm_index': self.fm_index.value() / 10.0,
            },
            'unison': {
                'voices': self.unison_voices.value(),
                'detune_cents': self.detune_cents.value(),
            },
            'sample_path': getattr(self.audio_engine.mixer.voices[0], 'sample_path', None),
            'sample_root_midi': self.sample_root_note.value(),
            'master_volume': self.volume_slider.value() / 100.0,
            'distortion': {
                'effect': self.distortion_selector.currentData(),
                'drive': self.distortion_drive_slider.value() / 100.0,
                'mix': self.distortion_mix_slider.value() / 100.0,
            },
            'delay': {
                'enabled': self.delay_enabled_selector.currentData(),
                'time_ms': self.delay_time_slider.value(),
                'feedback': self.delay_feedback_slider.value() / 100.0,
                'mix': self.delay_mix_slider.value() / 100.0,
            },
            'chorus': {
                'enabled': self.chorus_enabled_selector.currentData(),
                'rate_hz': self.chorus_rate_slider.value() / 10.0,
                'depth_ms': self.chorus_depth_slider.value() / 10.0,
                'mix': self.chorus_mix_slider.value() / 100.0,
            },
            'reverb': {
                'enabled': self.reverb_enabled_selector.currentData(),
                'decay_seconds': self.reverb_decay_slider.value() / 10.0,
                'mix': self.reverb_mix_slider.value() / 100.0,
            },
            'harmonic_mode': self.harmonic_mode.value,
            'chord_type': self.chord_type.value,
            'adsr': {
                'attack': self.attack_time,
                'decay': self.decay_time,
                'sustain': self.sustain_level,
                'release': self.release_time,
            },
            'filter': {
                'kind': self.filter_selector.currentText(),
                'cutoff': self.cutoff_slider.value(),
                'resonance': self.resonance_slider.value() / 100.0,
            },
            'lfo': {
                'target': self.lfo_target_selector.currentText(),
                'frequency': self.lfo_rate_slider.value() / 10.0,
                'depth': self.lfo_depth_slider.value() / 100.0,
            },
        }

    def _apply_preset_state(self, state: dict) -> None:
        """Apply a preset state to the GUI and engine."""
        self.audio_engine.begin_update_batch()
        try:
            self._apply_preset_controls(state)
        except Exception:
            self.audio_engine.cancel_update_batch()
            raise
        self.audio_engine.commit_update_batch()

    def _apply_preset_controls(self, state: dict) -> None:
        """Update controls while the engine collects one preset transaction."""
        if 'waveform' in state:
            self.oscillator_selector.setCurrentText(state['waveform'])
            self.audio_engine.set_oscillator_type(state['waveform'])
        if 'synthesis' in state:
            synthesis = state['synthesis']
            self.synthesis_mode_selector.setCurrentText(
                synthesis.get('mode', self.synthesis_mode_selector.currentText())
            )
            self.additive_partials.setValue(int(synthesis.get(
                'additive_partials', self.additive_partials.value()
            )))
            self.additive_tilt.setValue(int(round(float(synthesis.get(
                'additive_tilt_db_per_octave', self.additive_tilt.value() / 10.0
            )) * 10)))
            self.fm_ratio.setValue(int(round(float(synthesis.get(
                'fm_ratio', self.fm_ratio.value() / 10.0
            )) * 10)))
            self.fm_index.setValue(int(round(float(synthesis.get(
                'fm_index', self.fm_index.value() / 10.0
            )) * 10)))
            self.audio_engine.set_synthesis_mode(
                self.synthesis_mode_selector.currentText()
            )
            self.audio_engine.set_synthesis_parameters(
                self.additive_partials.value(),
                self.additive_tilt.value() / 10.0,
                self.fm_ratio.value() / 10.0,
                self.fm_index.value() / 10.0,
            )
        elif 'waveform' in state:
            self.synthesis_mode_selector.setCurrentText('waveform')
            self.audio_engine.set_synthesis_mode('waveform')
        if 'unison' in state:
            unison = state['unison']
            self.unison_voices.setValue(int(unison.get(
                'voices', self.unison_voices.value()
            )))
            self.detune_cents.setValue(int(unison.get(
                'detune_cents', self.detune_cents.value()
            )))
            self.audio_engine.set_unison_parameters(
                self.unison_voices.value(),
                self.detune_cents.value(),
            )

        if 'sample_root_midi' in state:
            self.sample_root_note.setValue(int(state['sample_root_midi']))
        sample_path = state.get('sample_path')
        if sample_path and Path(sample_path).is_file():
            try:
                self.audio_engine.load_sample(
                    sample_path,
                    self.note_mapper.midi_to_frequency(self.sample_root_note.value()),
                )
                self._set_sample_loaded_ui(Path(sample_path).name)
            except (OSError, ValueError, wave.Error) as error:
                self.statusBar().showMessage(f"Could not load preset sample: {error}")
                self.audio_engine.clear_sample()
                self._set_sample_loaded_ui(None)
        else:
            self.audio_engine.clear_sample()
            self._set_sample_loaded_ui(None)
        if 'master_volume' in state:
            volume_value = int(round(state['master_volume'] * 100))
            self.volume_slider.setValue(volume_value)
        if 'distortion' in state:
            distortion = state['distortion']
            effect_index = self.distortion_selector.findData(
                distortion.get('effect', self.distortion_selector.currentData())
            )
            if effect_index >= 0:
                self.distortion_selector.setCurrentIndex(effect_index)
            self.distortion_drive_slider.setValue(int(round(
                distortion.get('drive', self.distortion_drive_slider.value() / 100.0) * 100
            )))
            self.distortion_mix_slider.setValue(int(round(
                distortion.get('mix', self.distortion_mix_slider.value() / 100.0) * 100
            )))
        if 'delay' in state:
            delay = state['delay']
            enabled_index = self.delay_enabled_selector.findData(
                bool(delay.get('enabled', self.delay_enabled_selector.currentData()))
            )
            if enabled_index >= 0:
                self.delay_enabled_selector.setCurrentIndex(enabled_index)
            self.delay_time_slider.setValue(int(round(
                delay.get('time_ms', self.delay_time_slider.value())
            )))
            self.delay_feedback_slider.setValue(int(round(
                delay.get('feedback', self.delay_feedback_slider.value() / 100.0) * 100
            )))
            self.delay_mix_slider.setValue(int(round(
                delay.get('mix', self.delay_mix_slider.value() / 100.0) * 100
            )))
        if 'chorus' in state:
            chorus = state['chorus']
            enabled_index = self.chorus_enabled_selector.findData(
                bool(chorus.get('enabled', self.chorus_enabled_selector.currentData()))
            )
            if enabled_index >= 0:
                self.chorus_enabled_selector.setCurrentIndex(enabled_index)
            self.chorus_rate_slider.setValue(int(round(
                chorus.get('rate_hz', self.chorus_rate_slider.value() / 10.0) * 10
            )))
            self.chorus_depth_slider.setValue(int(round(
                chorus.get('depth_ms', self.chorus_depth_slider.value() / 10.0) * 10
            )))
            self.chorus_mix_slider.setValue(int(round(
                chorus.get('mix', self.chorus_mix_slider.value() / 100.0) * 100
            )))
        if 'reverb' in state:
            reverb = state['reverb']
            enabled_index = self.reverb_enabled_selector.findData(
                bool(reverb.get('enabled', self.reverb_enabled_selector.currentData()))
            )
            if enabled_index >= 0:
                self.reverb_enabled_selector.setCurrentIndex(enabled_index)
            self.reverb_decay_slider.setValue(int(round(
                reverb.get(
                    'decay_seconds', self.reverb_decay_slider.value() / 10.0
                ) * 10
            )))
            self.reverb_mix_slider.setValue(int(round(
                reverb.get('mix', self.reverb_mix_slider.value() / 100.0) * 100
            )))
        if 'harmonic_mode' in state:
            self.mode_selector.setCurrentText(state['harmonic_mode'])
        if 'chord_type' in state:
            self.chord_selector.setCurrentText(state['chord_type'])
        if 'adsr' in state:
            adsr = state['adsr']
            self.attack_time = adsr.get('attack', self.attack_time)
            self.decay_time = adsr.get('decay', self.decay_time)
            self.sustain_level = adsr.get('sustain', self.sustain_level)
            self.release_time = adsr.get('release', self.release_time)
            self.adsr_sliders['attack'].setValue(int(round(self.attack_time * 100)))
            self.adsr_sliders['decay'].setValue(int(round(self.decay_time * 100)))
            self.adsr_sliders['sustain'].setValue(int(round(self.sustain_level * 100)))
            self.adsr_sliders['release'].setValue(int(round(self.release_time * 100)))
        if 'filter' in state:
            filt = state['filter']
            self.filter_selector.setCurrentText(filt.get('kind', self.filter_selector.currentText()))
            self.cutoff_slider.setValue(int(round(filt.get('cutoff', self.cutoff_slider.value()))))
            self.resonance_slider.setValue(int(round(filt.get('resonance', self.resonance_slider.value() / 100.0) * 100)))
        if 'lfo' in state:
            lfo = state['lfo']
            self.lfo_target_selector.setCurrentText(lfo.get('target', self.lfo_target_selector.currentText()))
            rate = int(round(lfo.get('frequency', self.lfo_rate_slider.value() / 10.0) * 10))
            depth = int(round(lfo.get('depth', self.lfo_depth_slider.value() / 100.0) * 100))
            self.lfo_rate_slider.setValue(rate)
            self.lfo_depth_slider.setValue(depth)

    def _on_save_preset(self) -> None:
        """Save the current state as a preset."""
        name = self.preset_name_input.currentText().strip()
        if not name:
            return
        self.preset_manager.save_preset(name, self._collect_preset_state())
        self._refresh_preset_list(name)
        self.statusBar().showMessage(f"Saved preset: {name}")

    def _on_load_preset(self) -> None:
        """Load a preset into the UI and engine."""
        name = self.preset_name_input.currentText().strip()
        if not name:
            return
        try:
            state = self.preset_manager.load_preset(name)
        except FileNotFoundError:
            self.statusBar().showMessage(f"Preset not found: {name}")
            return
        self._apply_preset_state(state)
        self._refresh_preset_list(name)
        self.statusBar().showMessage(f"Loaded preset: {name}")

    def _refresh_preset_list(self, selected_name: Optional[str] = None) -> None:
        """Refresh the preset combo box contents."""
        presets = self.preset_manager.get_available_presets()
        current = self.preset_name_input.currentText()
        self.preset_name_input.clear()
        self.preset_name_input.addItems(presets)
        name_to_select = selected_name if selected_name is not None else current
        preset_index = self.preset_name_input.findText(name_to_select)
        if preset_index >= 0:
            self.preset_name_input.setCurrentIndex(preset_index)
        elif selected_name is not None or current not in presets:
            self.preset_name_input.setCurrentText(name_to_select)

    def _navigate_presets(self, direction: int) -> bool:
        """Load the adjacent preset, wrapping at either end of the list."""
        preset_count = self.preset_name_input.count()
        if preset_count == 0:
            return False

        current_index = self.preset_name_input.currentIndex()
        if current_index < 0:
            next_index = 0 if direction > 0 else preset_count - 1
        else:
            next_index = (current_index + direction) % preset_count

        self.preset_name_input.setCurrentIndex(next_index)
        self._on_load_preset()
        return True

    @pyqtSlot()
    def _update_status(self) -> None:
        """Update the status bar and refresh the waveform only when visible."""
        if self.is_running:
            # Update status bar
            status_text = (
                f"Run | SR: {self.audio_engine.sample_rate}Hz | "
                f"Buffer: {self.audio_engine.buffer_size} | "
                f"Latency: {self.audio_engine.buffer_size * 1000 / self.audio_engine.sample_rate:.1f}ms"
            )
            self.statusBar().showMessage(status_text)

        if (
            self.is_running
            and self.hex_window.scope_group.isVisible()
            and hasattr(self.audio_engine, 'get_waveform_buffer')
        ):
            self.scope_widget.set_samples(self.audio_engine.get_waveform_buffer())

    @pyqtSlot()
    def _update_audio_monitor(self) -> None:
        """Refresh callback metrics less frequently than the live waveform."""
        if self.is_running and self.hex_window.scope_group.isVisible():
            info = self.audio_engine.get_audio_info()
            self.monitor_label.setText(
                f"Voices: {info['active_voices']}/32\n"
                f"Callback P95: {info['callback_p95_ms']:.2f}/"
                f"{info['callback_budget_ms']:.2f} ms "
                f"({info['callback_p95_budget_percent']:.0f}%)\n"
                f"Mean/Max: {info['callback_mean_ms']:.2f}/"
                f"{info['callback_max_ms']:.2f} ms\n"
                f"Over budget: {info['callback_recent_deadline_misses']}/"
                f"{info['callback_window_size']} recent "
                f"({info['callback_recent_deadline_miss_percent']:.0f}%)\n"
                f"Total over budget: {info['callback_deadline_misses']}"
            )

    def _text_input_has_focus(self) -> bool:
        focused_widget = self._app.focusWidget()
        while focused_widget is not None:
            if isinstance(focused_widget, QLineEdit):
                return True
            if isinstance(focused_widget, QComboBox) and focused_widget.isEditable():
                return True
            focused_widget = focused_widget.parentWidget()
        return False

    def eventFilter(self, watched, event) -> bool:
        """Route preset navigation and note keys from the application windows."""
        if (
            event.type() == QEvent.Type.KeyPress
            and self._app.activeWindow() is self.hex_window
            and not self._text_input_has_focus()
        ):
            preset_directions = {
                Qt.Key.Key_Left: -1,
                Qt.Key.Key_Right: 1,
            }
            direction = preset_directions.get(event.key())
            if direction is not None:
                self._navigate_presets(direction)
                return True

        if (
            event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)
            and self._app.activeWindow() in (self, self.hex_window)
            and not self._text_input_has_focus()
        ):
            if event.type() == QEvent.Type.KeyPress:
                if self.keyboard_listener.handle_key_press(event):
                    return True
            elif self.keyboard_listener.handle_key_release(event):
                return True
        return super().eventFilter(watched, event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Override key press event."""
        if not event.isAutoRepeat():
            if self.keyboard_listener.handle_key_press(event):
                return
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Override key release event."""
        if not event.isAutoRepeat():
            if self.keyboard_listener.handle_key_release(event):
                return
        super().keyReleaseEvent(event)
    
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._app.removeEventFilter(self)
        self.hex_window.close()
        self._shutdown_resources()
        event.accept()
