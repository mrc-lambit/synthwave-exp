from types import SimpleNamespace

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from gui.main_window import MainWindow


def test_main_window_creates_hex_grid_window():
    window = MainWindow()
    assert hasattr(window, 'hex_window')
    assert window.hex_window is not None
    window.close()


def test_notes_work_while_hex_window_is_active():
    window = MainWindow()
    try:
        window.show()
        window.hex_window.show()
        window.hex_window.activateWindow()
        QTest.qWait(50)

        QTest.keyPress(window.hex_window, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == [60]
        QTest.keyRelease(window.hex_window, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == []

        window.activateWindow()
        preset_edit = window.preset_name_input.lineEdit()
        preset_edit.clear()
        preset_edit.setFocus()
        QTest.qWait(25)
        QTest.keyClick(preset_edit, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == []
        assert window.preset_name_input.currentText().lower() == 'a'
    finally:
        window.close()


def test_keyboard_plays_new_notes_after_live_parameter_change():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine.is_running = True
        window.show()
        window.activateWindow()
        QTest.qWait(25)

        QTest.keyPress(window, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == [60]
        window._on_filter_changed('lowpass', 5000, 0.0)
        window.cutoff_slider.setFocus()
        QTest.keyRelease(window.cutoff_slider, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == []

        QTest.keyPress(window, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == [60]
        output = np.zeros((512, 1), dtype=np.float32)
        window.audio_engine._audio_callback(
            output, 512, None, SimpleNamespace(output_underflow=False)
        )
        assert output.any()
    finally:
        window.close()


def test_keyboard_notes_work_after_changing_noneditable_selector():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine.is_running = True
        window.show()
        window.activateWindow()
        window.oscillator_selector.setCurrentText('square')
        window.oscillator_selector.setFocus()
        QTest.qWait(25)

        QTest.keyPress(window.oscillator_selector, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == [60]

        output = np.zeros((512, 1), dtype=np.float32)
        window.audio_engine._audio_callback(
            output, 512, None, SimpleNamespace(output_underflow=False)
        )
        assert output.any()
        QTest.keyRelease(window.oscillator_selector, Qt.Key.Key_A)
    finally:
        window.close()
