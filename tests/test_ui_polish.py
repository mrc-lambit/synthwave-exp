from PyQt6.QtWidgets import QComboBox, QDial, QLabel

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


def test_adsr_filter_and_master_effect_dials_use_compact_uniform_size():
    window = MainWindow()
    try:
        assert list(window.master_effect_groups) == [
            "distortion", "delay", "chorus", "reverb"
        ]
        selectors = [
            window.distortion_selector,
            window.delay_enabled_selector,
            window.chorus_enabled_selector,
            window.reverb_enabled_selector,
        ]
        assert all(
            selector.sizeAdjustPolicy()
            == QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            for selector in selectors
        )

        dials = [
            *window.adsr_sliders.values(),
            window.cutoff_slider,
            window.resonance_slider,
            window.distortion_drive_slider,
            window.distortion_mix_slider,
            window.delay_time_slider,
            window.delay_feedback_slider,
            window.delay_mix_slider,
            window.chorus_rate_slider,
            window.chorus_depth_slider,
            window.chorus_mix_slider,
            window.reverb_decay_slider,
            window.reverb_mix_slider,
        ]

        assert all(dial.size().width() == 42 for dial in dials)
        assert all(dial.size().height() == 42 for dial in dials)

        window.show()
        window._app.processEvents()
        first_row = [
            window.adsr_group,
            window.filter_group,
            window.master_effect_groups["distortion"],
        ]
        second_row = [
            window.master_effect_groups["delay"],
            window.master_effect_groups["chorus"],
            window.master_effect_groups["reverb"],
        ]
        assert all(panel.isVisible() for panel in first_row + second_row)
        assert len({panel.height() for panel in first_row}) == 1
        assert len({panel.height() for panel in second_row}) == 1
        for key, selector in zip(window.master_effect_groups, selectors):
            panel = window.master_effect_groups[key]
            selector_label = next(
                label
                for label in panel.findChildren(QLabel)
                if label.text() in ("Type:", "Effect:")
            )
            assert selector.width() > 0
            assert selector.geometry().left() > selector_label.geometry().right()
    finally:
        window.close()
