from PyQt6.QtWidgets import QDial

from gui.main_window import MainWindow


def test_main_window_can_initialize():
    window = MainWindow()
    assert window is not None
    window.close()


def test_dials_and_xy_pad_preserve_lfo_preset_values():
    window = MainWindow()
    try:
        assert isinstance(window.volume_slider, QDial)
        assert all(isinstance(dial, QDial) for dial in window.adsr_sliders.values())
        assert isinstance(window.cutoff_slider, QDial)
        assert isinstance(window.resonance_slider, QDial)

        window.lfo_xy_pad.set_values(15, 60)
        assert window.lfo_rate_label.text() == "Rate: 1.5 Hz"
        assert window.lfo_depth_label.text() == "Depth: 60%"
        state = window._collect_preset_state()
        assert state["lfo"]["frequency"] == 1.5
        assert state["lfo"]["depth"] == 0.6

        window._apply_preset_state({"lfo": {"target": "filter", "frequency": 0.7, "depth": 0.2}})
        assert window.lfo_xy_pad.rate == 7
        assert window.lfo_xy_pad.depth == 20
        assert window.lfo_rate_label.text() == "Rate: 0.7 Hz"
        assert window.lfo_depth_label.text() == "Depth: 20%"
    finally:
        window.close()
