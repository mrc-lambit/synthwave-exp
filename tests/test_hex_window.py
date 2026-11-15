import wave
from types import SimpleNamespace

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QFileDialog, QSizePolicy

from core.preset_manager import PresetManager
from gui.main_window import MainWindow


def test_main_window_creates_hex_grid_window():
    window = MainWindow()
    assert hasattr(window, 'hex_window')
    assert window.hex_window is not None
    window.close()


def test_multi_sound_mode_hosts_shared_controls_and_discards_inactive_octaves():
    window = MainWindow()
    try:
        hive = window.hex_window
        assert window.preset_group.parentWidget() is hive.shared_controls
        assert window.sample_group.parentWidget() is hive.shared_controls
        assert window.recording_group.parentWidget() is hive.shared_controls

        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        assert hive.hex_canvas._layout_mode == "multi"
        assert window.multi_sound_config["group_count"] == 2
        assert window.audio_engine.multi_sound_config["group_count"] == 2

        hive.multi_group_count.setCurrentText("4")
        hive.multi_octave.setCurrentText("6")
        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("waveform")
        )
        assert window.multi_sound_config["groups"][3]["waveform"] == "sine"

        hive.multi_group_count.setCurrentText("2")
        assert len(window.multi_sound_config["groups"]) == 2
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("keyboard"))
        assert window.audio_engine.multi_sound_config is None
    finally:
        window.close()


def test_multi_sound_grid_uses_same_color_family_per_octave_group():
    window = MainWindow()
    try:
        canvas = window.hex_window.hex_canvas
        canvas.set_layout_mode("multi")
        canvas.set_multi_group_count(4)

        group_hues = [
            {canvas._color_for_note(48 + group * 12 + index).hue() for index in range(12)}
            for group in range(4)
        ]

        assert len(group_hues[0]) == 1
        assert len(group_hues[1]) == 1
        assert len(group_hues[2]) == 1
        assert len(group_hues[3]) == 1
        assert [next(iter(group)) for group in group_hues] == [0, 120, 220, 270]
    finally:
        window.close()


def test_multi_sound_grid_uses_corner_groups_and_active_octave_count():
    window = MainWindow()
    try:
        canvas = window.hex_window.hex_canvas
        canvas.set_layout_mode("multi")
        canvas.set_multi_group_count(2)
        assert [cell.midi_note for cell in canvas._cells] == list(range(48, 72))

        canvas.set_multi_group_count(4)
        assert [cell.midi_note for cell in canvas._cells] == list(range(48, 96))
        center_x, center_y = canvas.width() / 2, canvas.height() / 2
        group_centers = []
        for group in range(4):
            cells = [
                cell for cell in canvas._cells
                if 48 + group * 12 <= cell.midi_note < 60 + group * 12
            ]
            group_centers.append((
                sum(cell.x for cell in cells) / len(cells),
                sum(cell.y for cell in cells) / len(cells),
            ))
        assert group_centers[0][0] < center_x and group_centers[0][1] < center_y
        assert group_centers[1][0] > center_x and group_centers[1][1] < center_y
        assert group_centers[2][0] < center_x and group_centers[2][1] > center_y
        assert group_centers[3][0] > center_x and group_centers[3][1] > center_y
    finally:
        window.close()


def test_loading_preset_preserves_current_mode_and_multi_sources(tmp_path):
    window = MainWindow()
    try:
        window.preset_manager = PresetManager(str(tmp_path))
        window.hex_window.layout_combo.setCurrentIndex(
            window.hex_window.layout_combo.findData("multi")
        )
        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("waveform")
        )
        window.multi_waveform_selector.setCurrentText("triangle")
        state = window._collect_preset_state()
        window.preset_manager.save_preset("multi", state)
        saved = window.preset_manager.load_preset("multi")

        window.hex_window.layout_combo.setCurrentIndex(
            window.hex_window.layout_combo.findData("keyboard")
        )
        window._apply_preset_state(saved)

        assert window.hex_window.layout_combo.currentData() == "keyboard"
        assert window.multi_sound_config == saved["multi_sound"]
        assert window.audio_engine.multi_sound_config is None

        window.hex_window.layout_combo.setCurrentIndex(
            window.hex_window.layout_combo.findData("multi")
        )
        saved["note_hive_mode"] = "keyboard"
        window._apply_preset_state(saved)
        assert window.hex_window.layout_combo.currentData() == "multi"
        assert window.audio_engine.multi_sound_config == saved["multi_sound"]
    finally:
        window.close()


def test_multi_sound_waveforms_remain_independent_by_octave():
    window = MainWindow()
    try:
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        hive.multi_group_count.setCurrentText("4")

        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("waveform")
        )
        window.multi_waveform_selector.setCurrentText("triangle")
        hive.multi_octave.setCurrentText("4")
        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("waveform")
        )
        window.multi_waveform_selector.setCurrentText("sawtooth")

        groups = window.audio_engine.mixer.multi_sound_groups
        assert window.multi_sound_config["groups"][0]["waveform"] == "triangle"
        assert window.multi_sound_config["groups"][1]["waveform"] == "sawtooth"
        assert groups[0][0] == "triangle"
        assert groups[1][0] == "sawtooth"
    finally:
        window.close()


def test_multi_sound_samples_remain_independent_by_octave(tmp_path, monkeypatch):
    sample_paths = [tmp_path / "octave3.wav", tmp_path / "octave4.wav"]
    for path in sample_paths:
        with wave.open(str(path), "wb") as sample_file:
            sample_file.setnchannels(1)
            sample_file.setsampwidth(2)
            sample_file.setframerate(8000)
            sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        hive.multi_group_count.setCurrentText("4")
        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("sample")
        )
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *args, **kwargs: (str(sample_paths[0]), "WAV audio (*.wav)"),
        )
        window._on_load_sample()

        hive.multi_octave.setCurrentText("4")
        window.multi_source_selector.setCurrentIndex(
            window.multi_source_selector.findData("sample")
        )
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *args, **kwargs: (str(sample_paths[1]), "WAV audio (*.wav)"),
        )
        window._on_load_sample()

        groups = window.audio_engine.mixer.multi_sound_groups
        assert window.multi_sound_config["groups"][0]["sample_path"] == str(sample_paths[0])
        assert window.multi_sound_config["groups"][1]["sample_path"] == str(sample_paths[1])
        assert groups[0][3] == str(sample_paths[0].resolve())
        assert groups[1][3] == str(sample_paths[1].resolve())
    finally:
        window.close()


def test_multi_sound_chord_stays_on_root_octave_source(tmp_path):
    sample_path = tmp_path / "octave3.wav"
    with wave.open(str(sample_path), "wb") as sample_file:
        sample_file.setnchannels(1)
        sample_file.setsampwidth(2)
        sample_file.setframerate(8000)
        sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        window.multi_sound_config = {
            "group_count": 2,
            "groups": [
                {"octave": 3, "sample_path": str(sample_path)},
                {"octave": 4, "waveform": "triangle"},
            ],
        }
        window._apply_multi_sound_config()
        window.is_running = True
        window.audio_engine.is_running = True
        window.harmonic_mode = window.harmonic_mode.__class__.TRIAD
        window.chord_type = window.chord_type.__class__.MAJOR

        voices = window._start_note_voices(59, 0.5)

        assert len(voices) == 3
        assert all(voice.sample_path == str(sample_path.resolve()) for voice in voices)
    finally:
        window.is_running = False
        window.audio_engine.is_running = False
        window.close()


def test_multi_preset_updates_only_selected_octave_source(tmp_path):
    sample_paths = [tmp_path / f"sample_{index}.wav" for index in range(3)]
    for path in sample_paths:
        with wave.open(str(path), "wb") as sample_file:
            sample_file.setnchannels(1)
            sample_file.setsampwidth(2)
            sample_file.setframerate(8000)
            sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        hive.multi_group_count.setCurrentText("4")
        window.multi_sound_config = {
            "group_count": 4,
            "groups": [
                {"octave": 3, "sample_path": str(sample_paths[0])},
                {"octave": 4, "waveform": "sawtooth"},
                {"octave": 5, "waveform": "square"},
                {"octave": 6, "waveform": "sine"},
            ],
        }
        window._apply_multi_sound_config()
        hive.multi_octave.setCurrentText("4")

        preset = window._collect_preset_state()
        preset["sample_path"] = str(sample_paths[2])
        preset["multi_sound"] = {
            "group_count": 4,
            "groups": [
                {"octave": 3, "waveform": "triangle"},
                {"octave": 4, "sample_path": str(sample_paths[1])},
                {"octave": 5, "waveform": "sawtooth"},
                {"octave": 6, "waveform": "square"},
            ],
        }
        window._apply_preset_state(preset)

        groups = window.audio_engine.mixer.multi_sound_groups
        assert window.multi_sound_config["groups"][0] == {
            "octave": 3, "sample_path": str(sample_paths[0])
        }
        assert window.multi_sound_config["groups"][1] == {
            "octave": 4, "sample_path": str(sample_paths[1])
        }
        assert window.multi_source_selector.currentData() == "sample"
        assert groups[0][3] == str(sample_paths[0].resolve())
        assert groups[1][3] == str(sample_paths[1].resolve())
        assert window.audio_engine.mixer._global_sample is None

        preset["multi_sound"]["groups"][1] = {
            "octave": 4, "waveform": "triangle"
        }
        window._apply_preset_state(preset)

        groups = window.audio_engine.mixer.multi_sound_groups
        assert window.multi_sound_config["groups"][0] == {
            "octave": 3, "sample_path": str(sample_paths[0])
        }
        assert window.multi_sound_config["groups"][1] == {
            "octave": 4, "waveform": "triangle"
        }
        assert window.multi_source_selector.currentData() == "waveform"
        assert window.multi_waveform_selector.currentText() == "triangle"
        assert groups[0][3] == str(sample_paths[0].resolve())
        assert groups[1][0] == "triangle"
        assert groups[1][1] is None
        sample_voice = window.audio_engine.mixer.note_on(
            440.0, group_index=0
        )
        waveform_voice = window.audio_engine.mixer.note_on(
            440.0, group_index=1
        )
        assert sample_voice.sample is not None
        assert waveform_voice.sample is None
    finally:
        window.close()


def test_multi_preset_replaces_sample_on_sounding_voice(tmp_path):
    sample_paths = [
        tmp_path / "old.wav",
        tmp_path / "other_octave.wav",
        tmp_path / "preset.wav",
    ]
    for path in sample_paths:
        with wave.open(str(path), "wb") as sample_file:
            sample_file.setnchannels(1)
            sample_file.setsampwidth(2)
            sample_file.setframerate(8000)
            sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        window.multi_sound_config = {
            "group_count": 2,
            "groups": [
                {"octave": 3, "sample_path": str(sample_paths[0])},
                {"octave": 4, "sample_path": str(sample_paths[1])},
            ],
        }
        window._apply_multi_sound_config()
        voice = window.audio_engine.mixer.note_on(440.0, group_index=0)
        other_octave_voice = window.audio_engine.mixer.note_on(
            440.0, group_index=1
        )
        assert voice.sample_path == str(sample_paths[0].resolve())
        assert other_octave_voice.sample_path == str(sample_paths[1].resolve())

        window._apply_preset_state({
            "multi_sound": {
                "group_count": 2,
                "groups": [
                    {"octave": 3, "sample_path": str(sample_paths[2])},
                    {"octave": 4, "sample_path": str(sample_paths[1])},
                ],
            },
        })

        assert voice.sample_path == str(sample_paths[2].resolve())
        assert other_octave_voice.sample_path == str(sample_paths[1].resolve())
    finally:
        window.close()


def test_global_sample_preset_loads_into_selected_multi_octave(tmp_path):
    sample_paths = [
        tmp_path / "other-octave.wav",
        tmp_path / "old-selected.wav",
        tmp_path / "global-preset.wav",
    ]
    for sample_path in sample_paths:
        with wave.open(str(sample_path), "wb") as sample_file:
            sample_file.setnchannels(1)
            sample_file.setsampwidth(2)
            sample_file.setframerate(8000)
            sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        window.preset_manager = PresetManager(str(tmp_path / "presets"))
        window.preset_manager.save_preset("sample-preset", {
            "waveform": "sine",
            "sample_path": str(sample_paths[2]),
            "sample_root_midi": 60,
        })
        hive = window.hex_window
        hive.layout_combo.setCurrentIndex(hive.layout_combo.findData("multi"))
        hive.multi_group_count.setCurrentText("4")
        window.multi_sound_config["groups"][0] = {
            "octave": 3, "sample_path": str(sample_paths[0])
        }
        window.multi_sound_config["groups"][1] = {
            "octave": 4, "sample_path": str(sample_paths[1])
        }
        window._apply_multi_sound_config()
        other_voice = window.audio_engine.mixer.note_on(440.0, group_index=0)
        selected_voice = window.audio_engine.mixer.note_on(440.0, group_index=1)
        hive.multi_octave.setCurrentText("4")
        window.preset_name_input.setCurrentText("sample-preset")

        window._on_load_preset()

        group = window.multi_sound_config["groups"][1]
        assert group["sample_path"] == str(sample_paths[2])
        assert group["sample_root_midi"] == 60
        assert window.audio_engine.mixer.multi_sound_groups[1][3] == str(
            sample_paths[2].resolve()
        )
        assert selected_voice.sample_path == str(sample_paths[2].resolve())
        assert other_voice.sample_path == str(sample_paths[0].resolve())
    finally:
        window.close()


def test_preset_save_includes_only_active_sound_source_and_custom_midi(tmp_path):
    sample_path = tmp_path / "global.wav"
    with wave.open(str(sample_path), "wb") as sample_file:
        sample_file.setnchannels(1)
        sample_file.setsampwidth(2)
        sample_file.setframerate(8000)
        sample_file.writeframes(np.full(128, 12000, dtype="<i2").tobytes())

    window = MainWindow()
    try:
        window.preset_manager = PresetManager(str(tmp_path / "presets"))
        state = window._collect_preset_state()
        assert state["waveform"] == window.oscillator_selector.currentText()
        assert "multi_sound" not in state
        assert "sample_path" not in state
        assert "sample_root_midi" not in state
        assert "midi_cc_mappings" not in state
        window.preset_manager.save_preset("waveform", state)
        assert "waveform" in window.preset_manager.load_preset("waveform")

        window.midi_cc_mappings[21] = "filter_cutoff"
        custom_state = window._collect_preset_state()
        assert custom_state["midi_cc_mappings"] == {
            "lfo_depth": 1,
            "master_volume": 7,
            "filter_cutoff": 21,
        }
        window.preset_manager.save_preset("custom-midi", custom_state)
        assert "midi_cc_mappings" in window.preset_manager.load_preset("custom-midi")
        window.midi_cc_mappings = dict(window.DEFAULT_MIDI_CC_MAPPINGS)

        window.audio_engine.load_sample(str(sample_path), 440.0)
        sample_state = window._collect_preset_state()
        assert sample_state["sample_path"] == str(sample_path.resolve())
        assert sample_state["sample_root_midi"] == window.global_sample_root_midi
        assert "waveform" not in sample_state
        assert "multi_sound" not in sample_state
        window.preset_manager.save_preset("sample", sample_state)
        saved_sample_state = window.preset_manager.load_preset("sample")
        assert "waveform" not in saved_sample_state
        assert "multi_sound" not in saved_sample_state

        window.hex_window.layout_combo.setCurrentIndex(
            window.hex_window.layout_combo.findData("multi")
        )
        window.multi_sound_config = {
            "group_count": 2,
            "groups": [
                {"octave": 3, "sample_path": str(sample_path)},
                {"octave": 4, "waveform": "triangle"},
            ],
        }
        multi_state = window._collect_preset_state()
        assert "multi_sound" in multi_state
        assert "waveform" not in multi_state
        assert "sample_path" not in multi_state
        assert "sample_root_midi" not in multi_state
        window.preset_manager.save_preset("multi", multi_state)
        saved_multi_state = window.preset_manager.load_preset("multi")
        assert "waveform" not in saved_multi_state
        assert "sample_path" not in saved_multi_state
        assert "sample_root_midi" not in saved_multi_state
    finally:
        window.close()


def test_main_window_keeps_synthesis_in_left_column_and_filter_compact():
    window = MainWindow()
    try:
        grid = window.main_scroll_area.widget().layout().itemAt(0).layout()
        controls_column = grid.itemAtPosition(0, 0).widget()
        assert grid.getItemPosition(grid.indexOf(controls_column)) == (0, 0, 1, 2)
        assert controls_column.layout().itemAt(1).widget() is window.synthesis_group
        right_column = grid.itemAtPosition(0, 2).widget()
        assert right_column.layout().itemAt(0).widget() is window.filter_group
        assert right_column.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    finally:
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

        window.hex_window.activateWindow()
        preset_edit = window.preset_name_input.lineEdit()
        window.preset_name_input.setCurrentIndex(-1)
        preset_edit.clear()
        preset_edit.setFocus()
        QTest.qWait(25)
        QTest.keyClick(preset_edit, Qt.Key.Key_A)
        assert window.keyboard_listener.get_pressed_notes() == []
        assert window.preset_name_input.currentText().lower().startswith('a')
    finally:
        window.close()


def test_arrow_keys_navigate_and_load_presets_in_hex_window(tmp_path):
    window = MainWindow()
    try:
        manager = PresetManager(str(tmp_path))
        manager.save_preset('first', {'waveform': 'sine'})
        manager.save_preset('second', {'waveform': 'square'})
        window.preset_manager = manager
        window._refresh_preset_list('first')
        window.show()
        window.hex_window.show()
        window.hex_window.activateWindow()
        QTest.qWait(25)

        QTest.keyClick(window.hex_window, Qt.Key.Key_Right)

        assert window.preset_name_input.currentText() == 'second'
        assert window.oscillator_selector.currentText() == 'square'

        QTest.keyClick(window.hex_window, Qt.Key.Key_Right)

        assert window.preset_name_input.currentText() == 'first'
        assert window.oscillator_selector.currentText() == 'sine'

        QTest.keyClick(window.hex_window, Qt.Key.Key_Left)

        assert window.preset_name_input.currentText() == 'second'
        assert window.oscillator_selector.currentText() == 'square'
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
