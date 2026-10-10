import numpy as np
import pytest

from audio.mixer import Mixer
from gui.main_window import MainWindow


def test_default_distortion_preserves_existing_soft_clip():
    mixer = Mixer(max_voices=1)
    samples = np.array([-2.0, -0.5, 0.0, 0.5, 2.0], dtype=np.float32)

    assert np.allclose(mixer._apply_distortion(samples), np.tanh(samples))


@pytest.mark.parametrize(
    'effect', ['off', 'soft_clip', 'overdrive', 'hard_clip', 'fuzz', 'bitcrush']
)
def test_distortion_modes_return_finite_audio(effect):
    mixer = Mixer(max_voices=1)
    samples = np.linspace(-1.5, 1.5, 128, dtype=np.float32)
    mixer.set_distortion(effect, drive=0.7, mix=1.0)

    output = mixer._apply_distortion(samples)

    assert output.shape == samples.shape
    assert np.isfinite(output).all()


def test_zero_mix_bypasses_distortion():
    mixer = Mixer(max_voices=1)
    samples = np.array([-2.0, -0.25, 0.25, 2.0], dtype=np.float32)
    mixer.set_distortion('hard_clip', drive=1.0, mix=0.0)

    assert np.array_equal(mixer._apply_distortion(samples), samples)


def test_distortion_parameters_are_clamped_and_effect_is_validated():
    mixer = Mixer(max_voices=1)
    mixer.set_distortion('fuzz', drive=2.0, mix=-1.0)

    assert mixer.distortion_drive == 1.0
    assert mixer.distortion_mix == 0.0
    with pytest.raises(ValueError):
        mixer.set_distortion('unknown')


def test_gui_preset_round_trips_distortion_settings():
    window = MainWindow()
    try:
        window.distortion_selector.setCurrentIndex(
            window.distortion_selector.findData('fuzz')
        )
        window.distortion_drive_slider.setValue(65)
        window.distortion_mix_slider.setValue(80)
        state = window._collect_preset_state()

        window._apply_preset_state(state)

        assert state['distortion'] == {'effect': 'fuzz', 'drive': 0.65, 'mix': 0.8}
        assert window.audio_engine.mixer.distortion_type == 'fuzz'
        assert window.audio_engine.mixer.distortion_drive == 0.65
        assert window.audio_engine.mixer.distortion_mix == 0.8
    finally:
        window.close()