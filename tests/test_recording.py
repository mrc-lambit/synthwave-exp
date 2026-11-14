from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np
import pytest

from audio.engine import AudioEngine


def test_audio_engine_can_record(tmp_path):
    engine = AudioEngine(sample_rate=22050, buffer_size=256, max_voices=8)
    output_path = tmp_path / 'demo.wav'
    engine.start_recording(str(output_path))
    engine.stop_recording()
    assert output_path.exists()


def test_audio_callback_queues_samples_and_flushes_wav(tmp_path):
    engine = AudioEngine(sample_rate=22050, buffer_size=256, max_voices=1)
    output_path = tmp_path / 'callback.wav'
    engine.mixer.note_on(440.0)
    engine.start_recording(str(output_path))
    output = np.zeros((256, 1), dtype=np.float32)

    engine._audio_callback(
        output, 256, None, SimpleNamespace(output_underflow=False)
    )
    recording_error = engine.stop_recording()

    assert recording_error is None
    assert output.any()
    with wave.open(str(output_path), 'rb') as recorded:
        assert recorded.getnframes() == 256
        assert np.frombuffer(recorded.readframes(256), dtype='<i2').any()


def test_audio_loop_wraps_and_is_included_in_new_recording(tmp_path):
    sample_rate = 8000
    loop_path = tmp_path / "loop.wav"
    loop_samples = np.array([1000, 2000, 3000, 4000], dtype="<i2")
    with wave.open(str(loop_path), "wb") as loop_file:
        loop_file.setnchannels(1)
        loop_file.setsampwidth(2)
        loop_file.setframerate(sample_rate)
        loop_file.writeframes(loop_samples.tobytes())

    engine = AudioEngine(sample_rate=sample_rate, buffer_size=4, max_voices=1)
    engine.load_loop(str(loop_path))
    engine.play_loop()
    engine.mixer.note_on(440.0)
    recording_path = tmp_path / "overdub.wav"
    engine.start_recording(str(recording_path))
    output = np.zeros((6, 1), dtype=np.float32)

    engine._audio_callback(
        output, 6, None, SimpleNamespace(output_underflow=False)
    )
    recording_error = engine.stop_recording()

    assert recording_error is None
    assert output[0, 0] == pytest.approx(1000 / 32768 * 0.8, abs=1e-4)
    with wave.open(str(recording_path), "rb") as recorded:
        recorded_samples = np.frombuffer(
            recorded.readframes(6), dtype="<i2"
        )
    expected_recording = np.clip(
        output[:, 0] * (0.8 * 32767.0), -32768, 32767
    ).astype("<i2")
    assert np.array_equal(recorded_samples, expected_recording)

    engine.mixer.stop_all()
    next_output = np.zeros((4, 1), dtype=np.float32)
    engine._audio_callback(
        next_output, 4, None, SimpleNamespace(output_underflow=False)
    )
    assert next_output[:, 0] == pytest.approx(
        loop_samples[[2, 3, 0, 1]] / 32768 * 0.8, abs=1e-4
    )


def test_full_recording_queue_reports_error_without_interrupting_audio(tmp_path):
    engine = AudioEngine(sample_rate=22050, buffer_size=256, max_voices=1)
    engine.mixer.note_on(440.0)
    engine.start_recording(str(tmp_path / 'overflow.wav'))
    recording_queue = engine._recording_queue
    original_put_nowait = recording_queue.put_nowait

    def report_full(_item):
        from queue import Full

        raise Full

    recording_queue.put_nowait = report_full
    output = np.zeros((256, 1), dtype=np.float32)
    engine._audio_callback(
        output, 256, None, SimpleNamespace(output_underflow=False)
    )
    recording_queue.put_nowait = original_put_nowait
    recording_error = engine.stop_recording()

    assert output.any()
    assert isinstance(recording_error, RuntimeError)
    assert "could not keep up" in str(recording_error)


def test_recording_writer_error_is_returned_when_stopped(monkeypatch, tmp_path):
    class FailedWriter:
        def setnchannels(self, _channels):
            pass

        def setsampwidth(self, _width):
            pass

        def setframerate(self, _sample_rate):
            pass

        def writeframes(self, _samples):
            raise OSError("disk write failed")

        def close(self):
            pass

    monkeypatch.setattr(
        "audio.engine.wave.open",
        lambda *_args, **_kwargs: FailedWriter(),
    )
    engine = AudioEngine(sample_rate=22050, buffer_size=256, max_voices=1)
    engine.start_recording(str(tmp_path / "failed.wav"))
    engine._enqueue_recording_samples(np.ones(256, dtype=np.float32))

    recording_error = engine.stop_recording()

    assert isinstance(recording_error, OSError)
    assert str(recording_error) == "disk write failed"
