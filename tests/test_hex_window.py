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
