from pathlib import Path

from audio.engine import AudioEngine


def test_audio_engine_can_record(tmp_path):
    engine = AudioEngine(sample_rate=22050, buffer_size=256, max_voices=8)
    output_path = tmp_path / 'demo.wav'
    engine.start_recording(str(output_path))
    engine.stop_recording()
    assert output_path.exists()
