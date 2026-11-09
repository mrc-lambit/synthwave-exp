import numpy as np
import pytest

from audio.filter import Filter
from audio.voice import Voice


def test_voice_skips_filter_processing_by_default(monkeypatch):
    voice = Voice(sample_rate=48000, oscillator_type="sine")
    voice.note_on(440.0, 0.5)

    def fail_if_processed(samples, sample_rate):
        raise AssertionError("filter processing should be disabled")

    monkeypatch.setattr(voice.filter, "process", fail_if_processed)

    samples = voice.generate(32)

    assert samples.shape == (32,)
    assert np.isfinite(samples).all()


def test_voice_can_reenable_filter_processing(monkeypatch):
    voice = Voice(sample_rate=48000, oscillator_type="sine")
    voice.FILTER_PROCESSING_ENABLED = True
    voice.note_on(440.0, 0.5)
    calls = []
    process_filter = voice.filter.process

    def track_filter(samples, sample_rate):
        calls.append(sample_rate)
        return process_filter(samples, sample_rate)

    monkeypatch.setattr(voice.filter, "process", track_filter)

    voice.generate(32)

    assert calls == [48000]


def _tone_rms(kind, frequency, cutoff=1000.0, resonance=0.0):
    sample_rate = 48000
    phase = np.arange(sample_rate, dtype=np.float64)
    samples = np.sin(2.0 * np.pi * frequency * phase / sample_rate)
    audio_filter = Filter(kind, cutoff, resonance)
    output = np.concatenate([
        audio_filter.process(block, sample_rate)
        for block in np.array_split(samples, 8)
    ])
    return float(np.sqrt(np.mean(output[int(sample_rate * 0.2) :] ** 2)))


@pytest.mark.parametrize("kind", ["lowpass", "highpass", "bandpass"])
def test_filter_preserves_state_across_blocks(kind):
    samples = np.array([0.0, 0.5, -0.5, 0.25], dtype=np.float32)
    whole_filter = Filter(kind, cutoff=1000.0, resonance=0.4)
    split_filter = Filter(kind, cutoff=1000.0, resonance=0.4)

    whole = whole_filter.process(samples, sample_rate=44100)
    split = np.concatenate([
        split_filter.process(samples[:2], sample_rate=44100),
        split_filter.process(samples[2:], sample_rate=44100),
    ])

    assert whole.shape == samples.shape
    assert np.isfinite(whole).all()
    assert np.allclose(split, whole)
    assert split_filter._integrator_1 == pytest.approx(
        whole_filter._integrator_1
    )
    assert split_filter._integrator_2 == pytest.approx(
        whole_filter._integrator_2
    )


def test_lowpass_cutoff_and_resonance_change_frequency_response():
    low_frequency = _tone_rms("lowpass", 200.0, cutoff=500.0)
    high_frequency = _tone_rms("lowpass", 5000.0, cutoff=500.0)
    low_resonance = _tone_rms(
        "lowpass", 500.0, cutoff=500.0, resonance=0.0
    )
    high_resonance = _tone_rms(
        "lowpass", 500.0, cutoff=500.0, resonance=0.8
    )

    assert low_frequency > high_frequency * 3.0
    assert high_resonance > low_resonance * 2.0


@pytest.mark.parametrize("kind", ["lowpass", "highpass", "bandpass"])
def test_resonance_emphasizes_cutoff_in_each_filter_mode(kind):
    low_resonance = _tone_rms(
        kind, 1000.0, cutoff=1000.0, resonance=0.0
    )
    high_resonance = _tone_rms(
        kind, 1000.0, cutoff=1000.0, resonance=0.8
    )

    assert high_resonance > low_resonance * 2.0


def test_highpass_attenuates_low_frequencies():
    low_frequency = _tone_rms("highpass", 100.0, cutoff=1000.0)
    high_frequency = _tone_rms("highpass", 5000.0, cutoff=1000.0)

    assert high_frequency > low_frequency * 3.0


def test_bandpass_emphasizes_frequencies_near_cutoff():
    below_cutoff = _tone_rms("bandpass", 200.0, cutoff=1000.0)
    at_cutoff = _tone_rms("bandpass", 1000.0, cutoff=1000.0)
    above_cutoff = _tone_rms("bandpass", 5000.0, cutoff=1000.0)

    assert at_cutoff > below_cutoff * 2.0
    assert at_cutoff > above_cutoff * 2.0


@pytest.mark.parametrize("kind", ["lowpass", "highpass", "bandpass"])
def test_filter_remains_finite_at_high_cutoff_and_resonance(kind):
    audio_filter = Filter(kind, cutoff=20000.0, resonance=1.0)
    output = audio_filter.process(
        np.ones(512, dtype=np.float32),
        sample_rate=22050,
    )

    assert np.isfinite(output).all()
    assert np.max(np.abs(output)) < 100.0


def test_resonance_is_clamped_to_supported_range():
    assert Filter(resonance=-0.5).resonance == 0.0
    assert Filter(resonance=1.5).resonance == 1.0
