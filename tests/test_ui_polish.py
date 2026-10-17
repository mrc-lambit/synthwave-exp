from types import SimpleNamespace

import numpy as np
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDial, QLabel, QPushButton, QVBoxLayout

from gui.main_window import MainWindow


def test_main_window_can_initialize():
    window = MainWindow()
    assert window is not None
    window.close()


def test_mono_controls_default_and_persist_in_legacy_compatible_presets():
    window = MainWindow()
    try:
        assert window.voice_mode_selector.currentText() == "poly"
        assert not window.legato_checkbox.isChecked()
        assert isinstance(window.legato_checkbox, QCheckBox)
        assert window.portamento_time_input.value() == 0

        window.voice_mode_selector.setCurrentText("mono")
        window.legato_checkbox.setChecked(True)
        window.portamento_time_input.setValue(350)
        state = window._collect_preset_state()
        assert state["voice_mode"] == "mono"
        assert state["legato"] is True
        assert state["portamento_ms"] == 350

        window.voice_mode_selector.setCurrentText("poly")
        window.legato_checkbox.setChecked(False)
        window.portamento_time_input.setValue(0)
        window._apply_preset_state(state)
        assert window.voice_mode_selector.currentText() == "mono"
        assert window.legato_checkbox.isChecked()
        assert window.portamento_time_input.value() == 350

        window._apply_preset_state({})
        assert window.voice_mode_selector.currentText() == "mono"
        assert window.legato_checkbox.isChecked()
        assert window.portamento_time_input.value() == 350
    finally:
        window.close()


def test_parameter_changes_do_not_retrigger_held_notes():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine.is_running = True
        window._on_note_on(60, window.note_mapper.midi_to_frequency(60))
        voices_before = tuple(window.audio_engine.mixer.active_voices)
        assert len(voices_before) == 1

        window._on_volume_changed(65)
        window._on_oscillator_changed("square")
        window._on_adsr_changed("sustain", 0.6)
        window._on_filter_changed("lowpass", 4000, 0.2)
        window._on_lfo_changed(8, 20)

        assert tuple(window.audio_engine.mixer.active_voices) == voices_before
        assert voices_before[0].is_active

        window._on_note_off(60)
        window._on_note_on(62, window.note_mapper.midi_to_frequency(62))
        output = np.zeros((512, 1), dtype=np.float32)
        window.audio_engine._audio_callback(
            output, 512, None, SimpleNamespace(output_underflow=False)
        )
        assert output.any()
    finally:
        window.close()


def test_failed_audio_start_keeps_controls_stopped():
    window = MainWindow()
    try:
        def fail_to_start():
            raise RuntimeError("device unavailable")

        window.audio_engine.start = fail_to_start
        window._start_audio()

        assert not window.is_running
        assert not window.start_stop_btn.isChecked()
        assert "device unavailable" in window.statusBar().currentMessage()
    finally:
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


def test_live_preset_is_committed_as_one_audio_update():
    window = MainWindow()
    try:
        window.audio_engine.is_running = True
        window.audio_engine.stream = object()
        window._apply_preset_state({
            "filter": {"kind": "highpass", "cutoff": 3000, "resonance": 0.2},
            "lfo": {"target": "filter", "frequency": 0.8, "depth": 0.4},
        })

        assert window.audio_engine._pending_updates.qsize() == 1
        assert window.audio_engine.mixer.voice_settings["filter_kind"] == "lowpass"

        output = np.zeros((512, 1), dtype=np.float32)
        window.audio_engine._audio_callback(
            output, 512, None, SimpleNamespace(output_underflow=False)
        )
        settings = window.audio_engine.mixer.voice_settings
        assert settings["filter_kind"] == "highpass"
        assert settings["filter_cutoff"] == 3000
        assert settings["lfo_target"] == "filter"
        assert settings["lfo_frequency"] == 0.8
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


def test_audio_and_midi_controls_use_separate_tabs_and_selector_column():
    window = MainWindow()
    try:
        assert [
            window.control_tabs.tabText(index)
            for index in range(window.control_tabs.count())
        ] == ["Audio", "MIDI", "Sampler"]
        audio_page = window.control_tabs.widget(0)
        midi_page = window.control_tabs.widget(1)
        sampler_page = window.control_tabs.widget(2)
        assert window.oscillator_selector.parentWidget() is audio_page
        assert window.mode_selector.parentWidget() is audio_page
        assert window.chord_selector.parentWidget() is audio_page
        assert window.voice_label.parentWidget() is audio_page
        assert window.midi_input_selector.parentWidget() is midi_page
        assert window.sample_button.parentWidget() is sampler_page
        assert window.sample_root_note.parentWidget() is sampler_page
        assert any(
            button.text() == "Refresh"
            for button in midi_page.findChildren(QPushButton)
        )
        assert isinstance(window.preset_group.layout(), QVBoxLayout)

        window.show()
        window._app.processEvents()
        selectors = [
            window.oscillator_selector,
            window.mode_selector,
            window.chord_selector,
        ]
        assert len({selector.x() for selector in selectors}) == 1
        assert [selector.y() for selector in selectors] == sorted(
            selector.y() for selector in selectors
        )
        assert window.voice_label.y() > window.volume_label.y()
    finally:
        window.close()
