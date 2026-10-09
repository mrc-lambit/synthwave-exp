from gui.main_window import MainWindow


def test_main_window_can_initialize():
    window = MainWindow()
    assert window is not None
    window.close()
