# -*- coding: utf-8 -*-
"""
Main Window module for the MUSA synthesizer GUI.

Provides the primary user interface with:
- Audio engine controls (Start/Stop)
- Master volume slider
- Oscillator type selector
- Keyboard display/layout info
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QComboBox, QLabel, QStatusBar,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QKeyEvent

from audio.engine import AudioEngine
from core.keyboard_listener import KeyboardListener
from core.note_mapper import NoteMapper


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
        super().__init__()
        
        self.setWindowTitle("MUSA - Software Synthesizer")
        self.setGeometry(100, 100, 900, 600)
        
        # Audio engine
        self.audio_engine: AudioEngine = AudioEngine()
        
        # Keyboard listener
        self.keyboard_listener: KeyboardListener = KeyboardListener()
        self.note_mapper: NoteMapper = NoteMapper()
        
        # Track which voice is assigned to which MIDI note (for note_off routing)
        self.midi_note_voices: dict = {}
        
        # Connect keyboard signals to audio engine
        self._connect_keyboard_signals()
        
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
        
        # Control panel
        control_group = self._create_control_panel()
        main_layout.addWidget(control_group)
        
        # Keyboard layout display
        keyboard_display = self._create_keyboard_display()
        main_layout.addWidget(keyboard_display)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        main_layout.addStretch()
    
    def _create_control_panel(self) -> QGroupBox:
        """Create the control panel group."""
        group = QGroupBox("Audio Engine Controls")
        layout = QGridLayout()
        
        # Start/Stop button
        self.start_stop_btn = QPushButton("Start Audio")
        self.start_stop_btn.setCheckable(True)
        self.start_stop_btn.clicked.connect(self._on_start_stop_clicked)
        layout.addWidget(self.start_stop_btn, 0, 0)
        
        # Master volume
        layout.addWidget(QLabel("Master Volume:"), 0, 1)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.sliderMoved.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider, 0, 2)
        
        self.volume_label = QLabel("0.80")
        layout.addWidget(self.volume_label, 0, 3)
        
        # Oscillator selector
        layout.addWidget(QLabel("Waveform:"), 1, 0)
        self.oscillator_selector = QComboBox()
        self.oscillator_selector.addItems(["sine", "square", "triangle", "sawtooth"])
        self.oscillator_selector.currentTextChanged.connect(self._on_oscillator_changed)
        layout.addWidget(self.oscillator_selector, 1, 1)
        
        # Active voices display
        layout.addWidget(QLabel("Active Voices:"), 1, 2)
        self.voice_label = QLabel("0/32")
        layout.addWidget(self.voice_label, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_keyboard_display(self) -> QGroupBox:
        """Create keyboard layout display."""
        group = QGroupBox("Keyboard Layout (2 Active Octaves)")
        layout = QVBoxLayout()
        
        # Get layout info
        layout_info = self.keyboard_listener.get_key_layout()
        
        # Upper row
        upper_label = QLabel("<b>Upper Row (C5-B5): Z S X D C V G B H N J M</b>")
        layout.addWidget(upper_label)
        
        upper_text = " | ".join(
            f"<b>{info['key'].upper()}</b>: {info['note_name']} ({info['frequency']:.1f} Hz)"
            for info in layout_info['upper_row']
        )
        upper_display = QLabel(upper_text)
        upper_display.setStyleSheet("font-size: 9px; color: #0066cc;")
        layout.addWidget(upper_display)
        
        # Lower row
        lower_label = QLabel("<b>Lower Row (C4-B4): Q 2 W 3 E R 5 T 6 Y 7 U</b>")
        layout.addWidget(lower_label)
        
        lower_text = " | ".join(
            f"<b>{info['key'].upper()}</b>: {info['note_name']} ({info['frequency']:.1f} Hz)"
            for info in layout_info['lower_row']
        )
        lower_display = QLabel(lower_text)
        lower_display.setStyleSheet("font-size: 9px; color: #cc0000;")
        layout.addWidget(lower_display)
        
        group.setLayout(layout)
        return group
    
    def _connect_keyboard_signals(self) -> None:
        """Connect keyboard listener signals to audio engine."""
        self.keyboard_listener.note_on.connect(self._on_note_on)
        self.keyboard_listener.note_off.connect(self._on_note_off)
    
    @pyqtSlot(int, float)
    def _on_note_on(self, midi_note: int, frequency: float) -> None:
        """Handle note on event from keyboard."""
        if not self.is_running:
            return
        
        # Request a voice from the mixer
        voice_id = self.audio_engine.note_on(frequency, 0.5, self.oscillator_selector.currentText())
        self.midi_note_voices[midi_note] = voice_id
    
    @pyqtSlot(int)
    def _on_note_off(self, midi_note: int) -> None:
        """Handle note off event from keyboard."""
        if midi_note in self.midi_note_voices:
            voice_id = self.midi_note_voices[midi_note]
            self.audio_engine.note_off(voice_id)
            del self.midi_note_voices[midi_note]
    
    @pyqtSlot()
    def _on_start_stop_clicked(self) -> None:
        """Handle start/stop button click."""
        if self.is_running:
            self._stop_audio()
        else:
            self._start_audio()
    
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
        """Stop the audio engine."""
        self.audio_engine.stop()
        self.keyboard_listener.release_all_notes()
        self.midi_note_voices.clear()
        self.is_running = False
        self.start_stop_btn.setText("Start Audio")
        self.start_stop_btn.setChecked(False)
        self.statusBar().showMessage("Audio stopped ⏹")
    
    @pyqtSlot(int)
    def _on_volume_changed(self, value: int) -> None:
        """Handle volume slider change."""
        volume = value / 100.0
        self.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{volume:.2f}")
    
    @pyqtSlot(str)
    def _on_oscillator_changed(self, oscillator_type: str) -> None:
        """Handle oscillator type change."""
        self.audio_engine.set_oscillator_type(oscillator_type)
    
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
        if self.is_running:
            self._stop_audio()
        self.status_timer.stop()
        event.accept()

