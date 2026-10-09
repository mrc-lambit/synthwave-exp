from gui.main_window import MainWindow


def test_main_window_supports_scope():
    window = MainWindow()
    assert window is not None
    window.close()
