from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np

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
