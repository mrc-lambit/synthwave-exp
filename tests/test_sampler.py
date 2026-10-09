import wave

import numpy as np

from audio.voice import Voice
from audio.engine import AudioEngine


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


def test_voice_is_silent_until_sample_is_loaded():
    voice = Voice(sample_rate=8000)
    voice.note_on(440, 0.5)

    assert np.all(voice.generate(32) == 0)


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