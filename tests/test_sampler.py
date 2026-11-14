import wave

import numpy as np
import pytest
from PyQt6.QtWidgets import QFileDialog

from audio.voice import Voice
from audio.engine import AudioEngine
from gui.main_window import MainWindow


def _write_test_wav(path, sample_rate=8000):
    samples = np.full(256, 12000, dtype='<i2')
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())


def test_sample_voice_plays_loaded_wav_and_stops_at_end(tmp_path):
    sample_path = tmp_path / 'tone.wav'
    _write_test_wav(sample_path)
    voice = Voice(sample_rate=8000)
    voice.load_sample(str(sample_path), root_frequency=440)
    voice.note_on(440, 0.5)

    first_buffer = voice.generate(32)
    remainder = voice.generate(400)

    assert np.any(first_buffer != 0)
    assert np.all(remainder[300:] == 0)
    assert voice.sample_path == str(sample_path.resolve())


def test_sample_root_note_changes_playback_rate(tmp_path):
    sample_path = tmp_path / 'tone.wav'
    _write_test_wav(sample_path)
    voice = Voice(sample_rate=8000)
    voice.load_sample(str(sample_path), root_frequency=440)
    voice.note_on(880, 0.5)
    voice.generate(32)

    assert voice.sample_position == 64


def test_voice_uses_selected_oscillator_until_sample_is_loaded():
    voice = Voice(sample_rate=8000, oscillator_type='square')
    voice.note_on(440, 0.5)

    assert np.any(voice.generate(32) != 0)


def test_audio_engine_note_off_without_voice_stops_all_voices():
    engine = AudioEngine(max_voices=2)
    engine.is_running = True
    engine.note_on(440)

    engine.note_off()

    assert engine.get_active_voice_count() == 0


def test_mixer_accepts_sample_playback_mode(tmp_path):
    sample_path = tmp_path / 'tone.wav'
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=1)
    engine.load_sample(str(sample_path), root_frequency=440)
    engine.is_running = True

    voice = engine.note_on(440, 0.5, 'sample')

    assert voice is not None
    assert np.any(voice.generate(16) != 0)


def test_changing_sample_rate_preserves_loaded_sample_and_effect_settings(tmp_path):
    sample_path = tmp_path / 'tone.wav'
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=1)
    engine.load_sample(str(sample_path), root_frequency=440)
    engine.set_delay(True, time_ms=180, feedback=0.4, mix=0.35)
    engine.set_sample_rate(16000)

    voice = engine.mixer.voices[0]
    assert engine.sample_rate == 16000
    assert engine.mixer.sample_rate == 16000
    assert voice.sample_rate == 16000
    assert voice.sample is not None
    assert len(voice.sample) == 512
    assert voice.sample_path == str(sample_path.resolve())
    assert engine.mixer.delay_enabled
    assert engine.mixer.delay_time_ms == 180
    assert engine.mixer.delay_feedback == 0.4
    assert engine.mixer.delay_mix == 0.35


def test_loaded_audio_loop_is_resampled_when_sample_rate_changes(tmp_path):
    sample_path = tmp_path / "loop.wav"
    _write_test_wav(sample_path, sample_rate=8000)
    engine = AudioEngine(sample_rate=8000, max_voices=1)

    engine.load_loop(str(sample_path))
    engine.set_sample_rate(16000)

    assert engine.loop_path == sample_path.resolve()
    assert engine._loop_samples is not None
    assert len(engine._loop_samples) == 512
    assert not engine._loop_playing


def test_multi_sound_routes_octaves_to_waveform_and_sample(tmp_path):
    sample_path = tmp_path / "octave4.wav"
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=4)
    engine.set_multi_sound_config({
        "group_count": 2,
        "groups": [
            {"octave": 3, "waveform": "square"},
            {"octave": 4, "sample_path": str(sample_path), "sample_root_midi": 60},
        ],
    })
    engine.is_running = True

    octave3_voice = engine.note_on_for_midi_note(59, 440.0)
    octave4_voice = engine.note_on_for_midi_note(60, 440.0)

    assert octave3_voice is not None
    assert octave3_voice.oscillator_type == "square"
    assert octave3_voice.sample is None
    assert octave4_voice is not None
    assert octave4_voice.sample_path == str(sample_path.resolve())
    assert octave4_voice.sample_root_frequency == pytest.approx(261.6256, rel=1e-4)


def test_multi_sound_empty_and_unconfigured_octaves_are_silent():
    engine = AudioEngine(sample_rate=8000, max_voices=4)
    engine.set_multi_sound_config({
        "group_count": 2,
        "groups": [
            {"octave": 3},
            {"octave": 4, "waveform": "triangle"},
        ],
    })
    engine.is_running = True

    assert engine.note_on_for_midi_note(48, 130.81) is None
    assert engine.note_on_for_midi_note(60, 261.63) is not None
    assert engine.note_on_for_midi_note(72, 523.25) is None
    assert engine.note_on_for_midi_note(47, 123.47) is None
    assert engine.note_on_for_midi_note(96, 1046.5) is None


def test_multi_sound_configuration_is_queued_after_wav_preparation(tmp_path):
    sample_path = tmp_path / "octave3.wav"
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=2)
    engine.is_running = True
    engine.stream = object()

    engine.set_multi_sound_config({
        "group_count": 2,
        "groups": [
            {"octave": 3, "sample_path": str(sample_path)},
            {"octave": 4},
        ],
    })

    assert engine.multi_sound_config is not None
    assert engine.mixer.multi_sound_groups is None
    assert not engine._pending_updates.empty()
    engine._apply_pending_updates()
    assert engine.mixer.multi_sound_groups[0][1] is not None
    engine.stream = None


def test_multi_sound_groups_survive_sample_rate_change(tmp_path):
    sample_path = tmp_path / "octave3.wav"
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=2)
    engine.set_multi_sound_config({
        "group_count": 2,
        "groups": [
            {"octave": 3, "sample_path": str(sample_path)},
            {"octave": 4, "waveform": "sawtooth"},
        ],
    })

    engine.set_sample_rate(16000)

    assert engine.mixer.multi_sound_groups[0][1].size == 512
    assert engine.mixer.multi_sound_groups[1][0] == "sawtooth"


def test_clearing_multi_sound_restores_global_sample(tmp_path):
    sample_path = tmp_path / "global.wav"
    _write_test_wav(sample_path)
    engine = AudioEngine(sample_rate=8000, max_voices=2)
    engine.load_sample(str(sample_path), 440.0)
    engine.set_multi_sound_config({
        "group_count": 2,
        "groups": [{"octave": 3, "waveform": "square"}, {"octave": 4}],
    })
    engine.is_running = True
    engine.note_on_for_midi_note(48, 130.81)
    assert engine.mixer.voices[0].sample is None

    engine.clear_multi_sound_config()

    assert engine.mixer.multi_sound_groups is None
    assert all(voice.sample_path == str(sample_path.resolve()) for voice in engine.mixer.voices)
    assert engine.note_on(440.0) is not None


def test_note_on_for_midi_note_rejects_invalid_midi_note():
    engine = AudioEngine()
    with pytest.raises(ValueError, match="MIDI note"):
        engine.note_on_for_midi_note(128, 1000)


def test_gui_disables_oscillator_for_sample_and_restores_it_on_removal(tmp_path, monkeypatch):
    sample_path = tmp_path / 'tone.wav'
    _write_test_wav(sample_path)
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        'getOpenFileName',
        lambda *args, **kwargs: (str(sample_path), 'WAV audio (*.wav)'),
    )
    try:
        window._on_load_sample()

        assert not window.oscillator_selector.isEnabled()
        assert window.remove_sample_button.isEnabled()
        assert window.sample_label.text() == sample_path.name

        window._on_remove_sample()

        assert window.oscillator_selector.isEnabled()
        assert not window.remove_sample_button.isEnabled()
        assert window.audio_engine.mixer.voices[0].sample is None
        assert window.sample_label.text() == 'No sample loaded'
    finally:
        window.close()


def test_gui_loads_and_removes_audio_loop(tmp_path, monkeypatch):
    sample_path = tmp_path / "loop.wav"
    _write_test_wav(sample_path)
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(sample_path), "WAV audio (*.wav)"),
    )
    try:
        audio_layout = window.control_tabs.widget(0).layout()
        button_column = audio_layout.itemAt(0).layout()
        right_column = audio_layout.itemAt(1).layout()
        assert [
            button_column.itemAt(index).widget()
            for index in range(button_column.count())
        ] == [
            window.start_stop_btn,
            window.record_btn,
            window.load_loop_btn,
            window.play_loop_btn,
            window.remove_loop_btn,
        ]
        volume_column = right_column.itemAt(0).layout()
        assert volume_column.itemAt(1).widget() is window.volume_slider
        assert window.size().width() == 1300
        assert window.size().height() == 600

        window._on_load_loop()

        assert window.audio_engine.loop_path == sample_path.resolve()
        assert window.play_loop_btn.isEnabled()
        assert window.remove_loop_btn.isEnabled()
        assert sample_path.name in window.statusBar().currentMessage()

        window.play_loop_btn.click()
        assert window.audio_engine._loop_playing

        window._on_remove_loop()
        assert window.audio_engine.loop_path is None
        assert not window.play_loop_btn.isEnabled()
        assert not window.remove_loop_btn.isEnabled()
    finally:
        window.close()