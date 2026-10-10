import numpy as np

from audio.lfo import LFO
from audio.voice import Voice


def test_lfo_generation():
    lfo = LFO(sample_rate=48000, frequency=4.0, depth=0.5)
    values = lfo.generate(16)
    assert values.shape == (16,)
    assert np.all(values <= 1.0)
    assert np.all(values >= -1.0)


def test_voice_supports_lfo_modulation():
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_lfo_parameters(frequency=4.0, depth=0.25, target='pitch')
    voice.note_on(440.0, 0.5)
    samples = voice.generate(32)
    assert samples.shape == (32,)
    assert samples.dtype == np.float32


def test_voice_filter_lfo_modulation():
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_filter('lowpass', 1000.0, 0.0)
    voice.set_lfo_parameters(frequency=2.0, depth=0.5, target='filter')
    voice.note_on(440.0, 0.5)
    voice.generate(16)
    assert voice.filter.cutoff > 1000.0
