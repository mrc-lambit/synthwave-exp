import wave

import numpy as np
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