import numpy as np
import pytest

from audio.lfo import LFO
from audio.voice import Voice


def test_lfo_generation():
    lfo = LFO(sample_rate=48000, frequency=4.0, depth=0.5)
    values = lfo.generate(16)
    assert values.shape == (16,)
    assert values.dtype == np.float32
    assert np.all(values <= 1.0)
    assert np.all(values >= -1.0)


@pytest.mark.parametrize("waveform", ["sine", "square", "triangle", "sawtooth"])
def test_vectorized_lfo_matches_phase_evaluation(waveform):
    lfo = LFO(sample_rate=48000, frequency=17.0, depth=0.65, waveform=waveform)
    lfo.phase = 0.37
    phase_increment = lfo.frequency / lfo.sample_rate
    phases = np.arange(257, dtype=np.float32) * phase_increment + lfo.phase
    phases = np.mod(phases, 1.0)
    expected = np.array(
        [lfo._evaluate_phase(phase) for phase in phases],
        dtype=np.float32,
    ) * lfo.depth

    actual = lfo.generate(len(phases))

    assert np.allclose(actual, expected)
    assert lfo.phase == pytest.approx(
        np.mod(phases[-1] + phase_increment, 1.0)
    )


def test_voice_supports_lfo_modulation():
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_lfo_parameters(frequency=4.0, depth=0.25, target='pitch')
    voice.note_on(440.0, 0.5)
    samples = voice.generate(32)
    assert samples.shape == (32,)
    assert samples.dtype == np.float32


def test_voice_skips_lfo_generation_when_depth_is_zero(monkeypatch):
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.note_on(440.0, 0.5)

    def fail_if_generated(_num_samples):
        raise AssertionError("disabled LFO should not generate samples")

    monkeypatch.setattr(voice.lfo, "generate", fail_if_generated)

    samples = voice.generate(32)

    assert samples.shape == (32,)
    assert np.isfinite(samples).all()


def test_filter_target_lfo_is_skipped_with_filter_processing_disabled(monkeypatch):
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_filter('lowpass', 1000.0, 0.0)
    voice.set_lfo_parameters(frequency=2.0, depth=0.5, target='filter')
    voice.note_on(440.0, 0.5)

    def fail_if_generated(_num_samples):
        raise AssertionError("disabled filter LFO should not generate samples")

    monkeypatch.setattr(voice.lfo, "generate", fail_if_generated)

    voice.generate(16)

    assert voice.filter.cutoff == 1000.0


def test_voice_filter_lfo_modulation():
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.FILTER_PROCESSING_ENABLED = True
    voice.set_filter('lowpass', 1000.0, 0.0)
    voice.set_lfo_parameters(frequency=2.0, depth=0.5, target='filter')
    voice.note_on(440.0, 0.5)
    voice.generate(16)
    assert voice.filter.cutoff > 1000.0
