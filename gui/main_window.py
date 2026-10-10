# -*- coding: utf-8 -*-
"""
Main Window module for the MUSA synthesizer GUI.

Provides the primary user interface with:
- Audio engine controls (Start/Stop)
- Master volume slider
- Oscillator type selector
- Keyboard display/layout info
"""

import sys
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QComboBox, QLabel, QStatusBar,
    QGroupBox, QGridLayout
)

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QRectF
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QKeyEvent, QPainter, QPen, QColor

from audio.engine import AudioEngine
from core.chord_engine import ChordEngine, ChordType, HarmonicMode
from core.keyboard_listener import KeyboardListener
from core.note_mapper import NoteMapper
from core.preset_manager import PresetManager
from gui.hex_grid_window import HexGridWindow


class MainWindow(QMainWindow):
    """
    Main window for the MUSA software synthesizer.
    
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
        
        self.setWindowTitle("MUSA - Software Synthesizer")
        self.setGeometry(100, 100, 900, 600)
        
        # Audio engine
        self.audio_engine: AudioEngine = AudioEngine()

        self.attack_time = 0.01
        self.decay_time = 0.1
        self.sustain_level = 0.7
        self.release_time = 0.3
        
        # Keyboard listener
        self.keyboard_listener: KeyboardListener = KeyboardListener()
        self.note_mapper: NoteMapper = NoteMapper()
        self.chord_engine: ChordEngine = ChordEngine()
        self.preset_manager: PresetManager = PresetManager()
        self.harmonic_mode: HarmonicMode = HarmonicMode.SINGLE
        self.chord_type: ChordType = ChordType.MAJOR
        
        # Track all generated voices for each pressed key so chord tones stop together
        self.midi_note_voices: dict[int, list[int]] = {}
        
        # Connect keyboard signals to audio engine
        self._connect_keyboard_signals()

        self.hex_window = HexGridWindow(self.note_mapper)
        self.scope_widget = self.hex_window.scope_widget
        self.monitor_label = self.hex_window.monitor_label
        self.hex_window.hide()

        # Setup UI
        self._setup_ui()
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(100)  # Update every 100ms
        
        # Engine state
        self.is_running = False
    
    def _setup_ui(self) -> None:
        """Setup the main user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        main_grid = QGridLayout()
        main_layout.addLayout(main_grid)

        control_group = self._create_control_panel()
        main_grid.addWidget(control_group, 0, 0, 1, 1)

        adsr_group = self._create_adsr_panel()
        main_grid.addWidget(adsr_group, 0, 1, 1, 1)

        filter_group = self._create_filter_panel()
        main_grid.addWidget(filter_group, 1, 0, 1, 1)

        lfo_group = self._create_lfo_panel()
        main_grid.addWidget(lfo_group, 1, 1, 1, 1)

        distortion_group = self._create_distortion_panel()
        main_grid.addWidget(distortion_group, 2, 0, 1, 2)

        preset_row = QHBoxLayout()

        preset_group = self._create_preset_panel()
        preset_row.addWidget(preset_group, stretch=2)

        status_group = self._create_status_panel()
        preset_row.addWidget(status_group, stretch=1)
        
        main_grid.addLayout(preset_row, 3, 0, 1, 1)

        keyboard_display = self._create_keyboard_display()
        # main_layout.addWidget(keyboard_display)

        self.statusBar().showMessage("Ready")
        self._show_startup_banner()
        
        main_layout.addStretch()
    
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

    def _create_control_panel(self) -> QGroupBox:
        """Create the control panel group."""
        group = QGroupBox("Audio Engine Controls")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QGridLayout()
        
        # Start/Stop button
        self.start_stop_btn = QPushButton("Start Audio")
        self.start_stop_btn.setCheckable(True)
        self.start_stop_btn.clicked.connect(self._on_start_stop_clicked)
        layout.addWidget(self.start_stop_btn, 0, 0)

        self.record_btn = QPushButton("Record")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self.record_btn, 0, 1)
        
        # Master volume
        layout.addWidget(QLabel("Master Volume:"), 0, 2)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider, 0, 3)
        
        self.volume_label = QLabel("0.80")
        layout.addWidget(self.volume_label, 0, 4)
        
        # Oscillator selector
        layout.addWidget(QLabel("Waveform:"), 1, 0)
        self.oscillator_selector = QComboBox()
        self.oscillator_selector.addItems(["sine", "square", "triangle", "sawtooth"])
        self.oscillator_selector.currentTextChanged.connect(self._on_oscillator_changed)
        layout.addWidget(self.oscillator_selector, 1, 1)
        
        # Harmonic mode selector
        layout.addWidget(QLabel("Mode:"), 2, 0)
        self.mode_selector = QComboBox()
        self.mode_selector.addItems([mode.value for mode in HarmonicMode])
        self.mode_selector.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_selector, 2, 1)

        layout.addWidget(QLabel("Chord:"), 2, 2)
        self.chord_selector = QComboBox()
        self.chord_selector.addItems([chord.value for chord in ChordType])
        self.chord_selector.currentTextChanged.connect(self._on_chord_type_changed)
        layout.addWidget(self.chord_selector, 2, 3)

        # Active voices display
        layout.addWidget(QLabel("Active Voices:"), 3, 0)
        self.voice_label = QLabel("0/32")
        layout.addWidget(self.voice_label, 3, 1)
        
        group.setLayout(layout)
        return group
    
    def _create_adsr_panel(self) -> QGroupBox:
        """Create ADSR parameter controls."""
        group = QGroupBox("ADSR")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QGridLayout()

        labels = ["Attack", "Decay", "Sustain", "Release"]
        defaults = [0.01, 0.1, 0.7, 0.3]
        self.adsr_sliders = {}

        for index, (label, default_value) in enumerate(zip(labels, defaults)):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 200)
            slider.setValue(int(default_value * 100))
            slider.valueChanged.connect(lambda value, name=label.lower(): self._on_adsr_changed(name, value / 100.0))
            layout.addWidget(QLabel(label), index, 0)
            layout.addWidget(slider, index, 1)
            self.adsr_sliders[label.lower()] = slider

        group.setLayout(layout)
        return group

    def _create_filter_panel(self) -> QGroupBox:
        """Create filter controls."""
        group = QGroupBox("Filter")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QGridLayout()

        self.filter_selector = QComboBox()
        self.filter_selector.addItems(["lowpass", "highpass", "bandpass"])
        self.filter_selector.currentTextChanged.connect(self._on_filter_changed)
        layout.addWidget(QLabel("Type:"), 0, 0)
        layout.addWidget(self.filter_selector, 0, 1)

        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setRange(50, 20000)
        self.cutoff_slider.setValue(2000)
        self.cutoff_slider.valueChanged.connect(lambda value: self._on_filter_changed(self.filter_selector.currentText(), value))
        layout.addWidget(QLabel("Cutoff:"), 1, 0)
        layout.addWidget(self.cutoff_slider, 1, 1)

        self.resonance_slider = QSlider(Qt.Orientation.Horizontal)
        self.resonance_slider.setRange(0, 100)
        self.resonance_slider.setValue(0)
        self.resonance_slider.valueChanged.connect(lambda value: self._on_filter_changed(self.filter_selector.currentText(), self.cutoff_slider.value(), value / 100.0))
        layout.addWidget(QLabel("Resonance:"), 2, 0)
        layout.addWidget(self.resonance_slider, 2, 1)

        group.setLayout(layout)
        return group

    def _create_lfo_panel(self) -> QGroupBox:
        """Create LFO modulation controls."""
        group = QGroupBox("LFO")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QGridLayout()

        self.lfo_target_selector = QComboBox()
        self.lfo_target_selector.addItems(["pitch", "volume", "filter"])
        self.lfo_target_selector.currentTextChanged.connect(self._on_lfo_target_changed)
        layout.addWidget(QLabel("Target:"), 0, 0)
        layout.addWidget(self.lfo_target_selector, 0, 1)

        self.lfo_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.lfo_rate_slider.setRange(0, 20)
        self.lfo_rate_slider.setValue(0)
        self.lfo_rate_slider.valueChanged.connect(lambda value: self._on_lfo_changed(value, self.lfo_depth_slider.value()))
        layout.addWidget(QLabel("Rate (Hz):"), 1, 0)
        layout.addWidget(self.lfo_rate_slider, 1, 1)

        self.lfo_depth_slider = QSlider(Qt.Orientation.Horizontal)
        self.lfo_depth_slider.setRange(0, 100)
        self.lfo_depth_slider.setValue(0)
        self.lfo_depth_slider.valueChanged.connect(lambda value: self._on_lfo_changed(self.lfo_rate_slider.value(), value))
        layout.addWidget(QLabel("Depth:"), 2, 0)
        layout.addWidget(self.lfo_depth_slider, 2, 1)

        group.setLayout(layout)
        return group

    def _create_distortion_panel(self) -> QGroupBox:
        """Create master distortion controls."""
        group = QGroupBox("Master Distortion")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QGridLayout()

        self.distortion_selector = QComboBox()
        for label, effect in [
            ("Soft Clip", "soft_clip"),
            ("Overdrive", "overdrive"),
            ("Hard Clip", "hard_clip"),
            ("Fuzz", "fuzz"),
            ("Bitcrusher", "bitcrush"),
            ("Off", "off"),
        ]:
            self.distortion_selector.addItem(label, effect)
        self.distortion_selector.currentIndexChanged.connect(self._on_distortion_changed)
        layout.addWidget(QLabel("Effect:"), 0, 0)
        layout.addWidget(self.distortion_selector, 0, 1)

        self.distortion_drive_slider = QSlider(Qt.Orientation.Horizontal)
        self.distortion_drive_slider.setRange(0, 100)
        self.distortion_drive_slider.setValue(0)
        self.distortion_drive_slider.valueChanged.connect(self._on_distortion_changed)
        layout.addWidget(QLabel("Drive:"), 0, 2)
        layout.addWidget(self.distortion_drive_slider, 0, 3)
        self.distortion_drive_label = QLabel("0%")
        layout.addWidget(self.distortion_drive_label, 0, 4)

        self.distortion_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.distortion_mix_slider.setRange(0, 100)
        self.distortion_mix_slider.setValue(100)
        self.distortion_mix_slider.valueChanged.connect(self._on_distortion_changed)
        layout.addWidget(QLabel("Mix:"), 0, 5)
        layout.addWidget(self.distortion_mix_slider, 0, 6)
        self.distortion_mix_label = QLabel("100%")
        layout.addWidget(self.distortion_mix_label, 0, 7)

        group.setLayout(layout)
        return group

    def _create_preset_panel(self) -> QGroupBox:
        """Create preset save/load controls."""
        group = QGroupBox("Presets")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QHBoxLayout()

        self.preset_name_input = QComboBox()
        self.preset_name_input.setEditable(True)
        self.preset_name_input.addItems(self.preset_manager.get_available_presets())
        layout.addWidget(self.preset_name_input)

        save_btn = QPushButton("Save Preset")
        save_btn.clicked.connect(self._on_save_preset)
        layout.addWidget(save_btn)

        load_btn = QPushButton("Load Preset")
        load_btn.clicked.connect(self._on_load_preset)
        layout.addWidget(load_btn)

        group.setLayout(layout)
        return group

    def _create_status_panel(self) -> QGroupBox:
        """Create a compact live status summary."""
        group = QGroupBox("Live Status")
        group.setStyleSheet("QGroupBox { border: 1px solid #4c5cff; border-radius: 6px; padding-top: 8px; }")
        layout = QHBoxLayout()

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        self.mode_status_label = QLabel("Mode: Single")
        layout.addWidget(self.mode_status_label)

        self.lfo_status_label = QLabel("LFO: Off")
        layout.addWidget(self.lfo_status_label)

        group.setLayout(layout)
        return group

    def _connect_keyboard_signals(self) -> None:
        """Connect keyboard listener signals to audio engine."""
        self.keyboard_listener.note_on.connect(self._on_note_on)
        self.keyboard_listener.note_off.connect(self._on_note_off)
    
    @pyqtSlot(int, float)
    def _on_note_on(self, midi_note: int, frequency: float) -> None:
        """Handle note on event from keyboard."""
        self.hex_window.note_on(midi_note, frequency)

        if not self.is_running:
            return

        notes = self.chord_engine.get_notes_for_mode(
            midi_note,
            self.harmonic_mode,
            self.chord_type,
        )
        active_voice_ids: list[int] = []
        for note in notes:
            note_frequency = self.note_mapper.midi_to_frequency(note)
            voice_id = self.audio_engine.note_on(
                note_frequency,
                0.5,
                self.oscillator_selector.currentText(),
            )
            if voice_id is not None:
                active_voice_ids.append(voice_id)
        if active_voice_ids:
            self.midi_note_voices[midi_note] = active_voice_ids
    
    @pyqtSlot(int)
    def _on_note_off(self, midi_note: int) -> None:
        """Handle note off event from keyboard."""
        self.hex_window.note_off(midi_note)

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
            output_path = f"recordings/demo_{int(QTimer.currentTime())}.wav"
            self.audio_engine.start_recording(output_path)
            self.record_btn.setText("Stop Recording")
            self.statusBar().showMessage("Recording...")
        else:
            self.audio_engine.stop_recording()
            self.record_btn.setText("Record")
            self.statusBar().showMessage("Recording stopped")

    def _start_audio(self) -> None:
        """Start the audio engine."""
        try:
            self.audio_engine.start()
            self.is_running = True
            self.start_stop_btn.setText("Stop Audio")
            self.start_stop_btn.setChecked(True)
            self.statusBar().showMessage("Audio running ▶")
        except Exception as e:
            self.statusBar().showMessage(f"Error starting audio: {str(e)}")
    
    def _stop_audio(self) -> None:
        """Stop the audio engine and recording safely."""
        if self.record_btn.isChecked():
            self.audio_engine.stop_recording()
            self.record_btn.setChecked(False)
            self.record_btn.setText("Record")
        self.audio_engine.stop()
        self.keyboard_listener.release_all_notes()
        self.midi_note_voices.clear()
        self.is_running = False
        self.start_stop_btn.setText("Start Audio")
        self.start_stop_btn.setChecked(False)
        self.statusBar().showMessage("Audio stopped ⏹")

    def _shutdown_resources(self) -> None:
        """Stop audio, recording, timers, and pending notes during shutdown."""
        if self.status_timer.isActive():
            self.status_timer.stop()

        if self.is_running:
            self._stop_audio()
        else:
            self.audio_engine.stop_recording()

        self.keyboard_listener.release_all_notes()
        self.midi_note_voices.clear()
        self.audio_engine.stop()
        self.audio_engine.stop_recording()
    
    def _resync_pressed_notes(self) -> None:
        """Apply current synth settings immediately to all notes currently held down."""
        if not self.is_running:
            return

        pressed_notes = list(self.keyboard_listener.get_pressed_notes())
        for midi_note in pressed_notes:
            self._on_note_off(midi_note)
            self._on_note_on(midi_note, self.note_mapper.midi_to_frequency(midi_note))

    @pyqtSlot(int)
    def _on_volume_changed(self, value: int) -> None:
        """Handle volume slider change."""
        volume = value / 100.0
        self.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{volume:.2f}")
        self._resync_pressed_notes()
    
    @pyqtSlot(str)
    def _on_oscillator_changed(self, oscillator_type: str) -> None:
        """Handle oscillator type change."""
        self.audio_engine.set_oscillator_type(oscillator_type)
        self._resync_pressed_notes()

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

        self._resync_pressed_notes()

    @pyqtSlot(str)
    def _on_chord_type_changed(self, chord_name: str) -> None:
        """Handle chord quality changes."""
        try:
            self.chord_type = ChordType(chord_name)
        except ValueError:
            self.chord_type = ChordType.MAJOR

        self._resync_pressed_notes()

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
        self._resync_pressed_notes()

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
        self._resync_pressed_notes()

    @pyqtSlot(str)
    def _on_lfo_target_changed(self, target: str) -> None:
        """Handle LFO target selection."""
        self.audio_engine.set_lfo_parameters(
            frequency=self.lfo_rate_slider.value() / 10.0,
            depth=self.lfo_depth_slider.value() / 100.0,
            target=target,
        )
        self._resync_pressed_notes()

    def _on_lfo_changed(self, rate: int, depth: int) -> None:
        """Handle LFO rate/depth changes."""
        self.audio_engine.set_lfo_parameters(
            frequency=float(rate) / 10.0,
            depth=float(depth) / 100.0,
            target=self.lfo_target_selector.currentText(),
        )
        self._resync_pressed_notes()

    def _on_distortion_changed(self, _value: int = 0) -> None:
        """Apply master distortion settings immediately."""
        drive = self.distortion_drive_slider.value()
        mix = self.distortion_mix_slider.value()
        self.distortion_drive_label.setText(f"{drive}%")
        self.distortion_mix_label.setText(f"{mix}%")
        self.audio_engine.set_distortion(
            self.distortion_selector.currentData(), drive / 100.0, mix / 100.0
        )
    
    def _collect_preset_state(self) -> dict:
        """Collect the current synth state into a JSON-serializable dict."""
        return {
            'name': self.preset_name_input.currentText(),
            'oscillator_type': self.oscillator_selector.currentText(),
            'master_volume': self.volume_slider.value() / 100.0,
            'distortion': {
                'effect': self.distortion_selector.currentData(),
                'drive': self.distortion_drive_slider.value() / 100.0,
                'mix': self.distortion_mix_slider.value() / 100.0,
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
        if 'oscillator_type' in state:
            self.oscillator_selector.setCurrentText(state['oscillator_type'])
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
            self.lfo_rate_slider.setValue(int(round(lfo.get('frequency', self.lfo_rate_slider.value() / 10.0) * 10)))
            self.lfo_depth_slider.setValue(int(round(lfo.get('depth', self.lfo_depth_slider.value() / 100.0) * 100)))

        if self.is_running:
            self._resync_pressed_notes()

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
        if selected_name is not None:
            self.preset_name_input.setCurrentText(selected_name)
        elif current in presets:
            self.preset_name_input.setCurrentText(current)

    @pyqtSlot()
    def _update_status(self) -> None:
        """Update status bar with engine info."""
        if self.is_running:
            info = self.audio_engine.get_audio_info()
            active_voices = len(self.keyboard_listener.get_pressed_notes())
            self.voice_label.setText(f"{active_voices}/32")
            
            # Update status bar
            status_text = f"SR: {info['sample_rate']}Hz | Buffer: {info['buffer_size']} | Latency: {info['latency_ms']:.1f}ms | Voices: {active_voices}/32"
            self.statusBar().showMessage(status_text)
            self.status_label.setText("Running")
            self.mode_status_label.setText(f"Mode: {self.harmonic_mode.value}")
            self.lfo_status_label.setText(
                f"LFO: {self.lfo_target_selector.currentText()} @ {self.lfo_rate_slider.value()/10.0:.1f}Hz"
            )
            self.monitor_label.setText(
                f"Underruns: {info['underruns']}\nActive Voices: {info['active_voices']}"
            )
        else:
            self.status_label.setText("Idle")
            self.mode_status_label.setText(f"Mode: {self.harmonic_mode.value}")
            self.lfo_status_label.setText("LFO: Off")
            self.monitor_label.setText("Underruns: 0\nActive Voices: 0")

        if self.is_running and hasattr(self.audio_engine, 'get_waveform_buffer'):
            self.scope_widget.set_samples(self.audio_engine.get_waveform_buffer())
    
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
        self.hex_window.close()
        self._shutdown_resources()
        event.accept()

