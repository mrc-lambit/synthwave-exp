from types import SimpleNamespace

import numpy as np
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import (
    QComboBox,
    QDial,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from gui.main_window import MainWindow


def test_main_window_can_initialize():
    window = MainWindow()
    assert window is not None
    window.close()


def test_main_window_scrolls_controls_when_height_is_constrained():
    window = MainWindow()
    try:
        assert isinstance(window.centralWidget(), QScrollArea)
        assert window.main_scroll_area.widgetResizable()

        window.resize(1000, 600)
        window.show()
        window._app.processEvents()

        assert window.main_scroll_area.verticalScrollBar().maximum() > 0
    finally:
        window.close()


def test_audio_monitor_displays_callback_budget_metrics():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine._record_callback_timing(2_000_000, 128)

        window._update_status()

        assert "Callback P95:" in window.monitor_label.text()
        assert "Over budget: 0" in window.monitor_label.text()
        assert window.audio_engine.get_audio_info()["callback_count"] == 1
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
        assert window.audio_engine.mixer.voice_settings["lfo_frequency"] == 1.5
        state = window._collect_preset_state()
        assert state["lfo"]["frequency"] == 1.5
        assert state["lfo"]["depth"] == 0.6

        window._apply_preset_state({"lfo": {"target": "filter", "frequency": 0.7, "depth": 0.2}})
        assert window.lfo_xy_pad.rate == 7
        assert window.lfo_xy_pad.depth == 20
        assert window.lfo_rate_label.text() == "Rate: 0.7 Hz"
        assert window.lfo_depth_label.text() == "Depth: 20%"
        assert window.audio_engine.mixer.voice_settings["lfo_frequency"] == 0.7

        window.lfo_target_selector.setCurrentText("pitch")
        assert window.audio_engine.mixer.voice_settings["lfo_frequency"] == 0.7
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

        window.resize(1366, 727)
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

        selector_panels = [
            (window.lfo_target_selector, window.lfo_target_selector.parentWidget()),
            (window.filter_selector, window.filter_group),
            *(
                (selector, window.master_effect_groups[key])
                for key, selector in zip(window.master_effect_groups, selectors)
            ),
        ]
        selector_positions = {
            selector.mapTo(panel, QPoint(0, 0)).x()
            for selector, panel in selector_panels
        }
        assert max(selector_positions) - min(selector_positions) <= 1
    finally:
        window.close()


def test_audio_and_midi_controls_use_separate_tabs_and_selector_column():
    window = MainWindow()
    try:
        assert [
            window.control_tabs.tabText(index)
            for index in range(window.control_tabs.count())
        ] == ["Audio", "Engine / MIDI", "Sampler / Presets"]
        audio_page = window.control_tabs.widget(0)
        engine_page = window.control_tabs.widget(1)
        sampler_page = window.control_tabs.widget(2)
        assert window.synthesis_group.parentWidget() is not audio_page
        assert window.oscillator_selector.parentWidget() is window.synthesis_group
        assert window.synthesis_mode_selector.parentWidget() is window.synthesis_group
        assert window.additive_partials.parentWidget() is window.synthesis_group
        assert window.additive_tilt.parentWidget() is window.synthesis_group
        assert window.fm_ratio.parentWidget() is window.synthesis_group
        assert window.fm_index.parentWidget() is window.synthesis_group
        assert window.mode_selector.parentWidget() is audio_page
        assert window.chord_selector.parentWidget() is audio_page
        assert window.midi_input_selector.parentWidget() is engine_page
        assert window.buffer_size.parentWidget() is engine_page
        assert window.sample_rate_selector.parentWidget() is engine_page
        assert window.sample_button.parentWidget() is sampler_page
        assert window.sample_root_note.parentWidget() is sampler_page
        assert window.preset_name_input.parentWidget() is sampler_page
        assert window.synthesis_group.parentWidget() is not sampler_page
        assert window.unison_voices.parentWidget() is window.synthesis_group
        assert window.detune_cents.parentWidget() is window.synthesis_group
        assert not any(
            group.title() == "Presets"
            for group in sampler_page.findChildren(QGroupBox)
        )
        assert any(
            button.text() == "Refresh"
            for button in engine_page.findChildren(QPushButton)
        )
        assert {
            button.text()
            for button in sampler_page.findChildren(QPushButton)
        } >= {"Save Preset", "Load Preset"}

        window.control_tabs.setCurrentWidget(engine_page)
        window.show()
        window._app.processEvents()
        assert window.synthesis_group.isVisible()
        assert window.synthesis_mode_selector.isVisible()
        assert window.additive_partials.isVisible()
        assert window.fm_ratio.isVisible()
        assert window.unison_voices.isVisible()
        assert window.detune_cents.isVisible()
        selectors = [
            window.oscillator_selector,
            window.mode_selector,
            window.chord_selector,
            window.lfo_target_selector,
            window.sample_rate_selector,
            window.preset_name_input,
            window.filter_selector,
            window.distortion_selector,
            window.delay_enabled_selector,
            window.chorus_enabled_selector,
            window.reverb_enabled_selector,
        ]
        assert {selector.width() for selector in selectors} == {160}
        buttons = [
            window.start_stop_btn,
            window.record_btn,
            next(
                button for button in engine_page.findChildren(QPushButton)
                if button.text() == "Refresh"
            ),
            window.sample_button,
            window.remove_sample_button,
            *sampler_page.findChildren(QPushButton),
        ]
        assert {(button.width(), button.height()) for button in buttons} == {
            (120, 30)
        }

        midi_row = engine_page.layout().itemAt(0).layout()
        fixed_width = (
            midi_row.itemAt(0).widget().width()
            + midi_row.itemAt(3).widget().width()
            + midi_row.spacing() * (midi_row.count() - 1)
            + midi_row.contentsMargins().left()
            + midi_row.contentsMargins().right()
        )
        available_width = midi_row.geometry().width() - fixed_width
        assert abs(
            window.midi_input_selector.width() / available_width - 0.7
        ) < 0.03

        window.control_tabs.setCurrentWidget(sampler_page)
        window._app.processEvents()
        assert window.synthesis_group.isVisible()
        assert window.synthesis_mode_selector.isVisible()
        assert window.additive_partials.isVisible()
        assert window.fm_ratio.isVisible()
        assert window.unison_voices.isVisible()
        assert window.detune_cents.isVisible()
        assert window.preset_name_input.mapTo(
            sampler_page, QPoint(0, 0)
        ).y() < window.sample_button.mapTo(sampler_page, QPoint(0, 0)).y()
        assert next(
            button for button in sampler_page.findChildren(QPushButton)
            if button.text() == "Save Preset"
        ).mapTo(sampler_page, QPoint(0, 0)).y() < window.sample_button.mapTo(
            sampler_page, QPoint(0, 0)
        ).y()
        selectors = [
            window.mode_selector,
            window.chord_selector,
        ]
        assert len({selector.x() for selector in selectors}) == 1
        assert [selector.y() for selector in selectors] == sorted(
            selector.y() for selector in selectors
        )
    finally:
        window.close()


def test_engine_tab_updates_buffer_size_without_reusing_audio_layouts():
    window = MainWindow()
    try:
        assert [
            window.control_tabs.tabText(index)
            for index in range(window.control_tabs.count())
        ] == ["Audio", "Engine / MIDI", "Sampler / Presets"]
        audio_page = window.control_tabs.widget(0)
        engine_page = window.control_tabs.widget(1)
        assert window.oscillator_selector.parentWidget() is window.synthesis_group
        assert window.buffer_size.parentWidget() is engine_page
        assert window.buffer_size.value() == window.audio_engine.buffer_size

        window.buffer_size.setValue(512)

        assert window.audio_engine.buffer_size == 512
        assert window.buffer_size.isEnabled()

        window.sample_rate_selector.setCurrentIndex(
            window.sample_rate_selector.findData(48000)
        )

        assert window.audio_engine.sample_rate == 48000
        assert window.audio_engine.mixer.sample_rate == 48000
        assert all(voice.sample_rate == 48000 for voice in window.audio_engine.mixer.voices)
        assert window.audio_engine.mixer.reverb.sample_rate == 48000
    finally:
        window.close()
