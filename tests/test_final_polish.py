from gui.main_window import MainWindow


def test_main_window_initializes_and_closes():
    window = MainWindow()
    window.close()
    assert window is not None


def test_shutdown_cleanup_stops_timer_and_audio_state():
    window = MainWindow()
    window.is_running = True
    window.status_timer.start(100)
    window.audio_engine.start_recording("recordings/test_shutdown.wav")

    window._shutdown_resources()

    assert not window.is_running
    assert not window.status_timer.isActive()
    assert window.audio_engine.recording_file is None
