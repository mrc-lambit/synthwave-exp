from gui.main_window import MainWindow


def test_main_window_creates_hex_grid_window():
    window = MainWindow()
    assert hasattr(window, 'hex_window')
    assert window.hex_window is not None
    window.close()
