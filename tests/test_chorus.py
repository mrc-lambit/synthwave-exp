import numpy as np

from audio.mixer import Mixer
from gui.main_window import MainWindow


def test_chorus_fixed_depth_impulse_crosses_audio_blocks_at_25_ms():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, rate_hz=0.1, depth_ms=0.0, mix=1.0)
    blocks = [
        mixer._apply_chorus(np.r_[1.0, np.zeros(11)].astype(np.float32)),
        mixer._apply_chorus(np.zeros(12, dtype=np.float32)),
        mixer._apply_chorus(np.zeros(12, dtype=np.float32)),
    ]

    output = np.concatenate(blocks)

    assert output[25] == 1.0
    assert np.count_nonzero(output) == 1


def test_chorus_modulation_phase_continues_across_blocks():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, rate_hz=1.0, depth_ms=5.0, mix=1.0)
    mixer._apply_chorus(np.zeros(12, dtype=np.float32))
    mixer._apply_chorus(np.zeros(13, dtype=np.float32))

    assert np.isclose(mixer._chorus_phase, 2.0 * np.pi * 25 / 1000)


def test_chorus_mix_blends_dry_and_wet_signal():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, depth_ms=0.0, mix=0.4)

    output = mixer._apply_chorus(np.array([1.0], dtype=np.float32))

    assert np.allclose(output, [0.6])


def test_zero_mix_keeps_chorus_state_advancing():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, rate_hz=1.0, depth_ms=0.0, mix=0.0)
    samples = np.ones(12, dtype=np.float32)

    output = mixer._apply_chorus(samples)

    assert output is samples or np.array_equal(output, samples)
    assert mixer._chorus_phase > 0.0
    assert mixer._chorus_buffer.any()


def test_chorus_bypass_clears_buffer_and_preserves_input():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, depth_ms=0.0, mix=1.0)
    mixer._apply_chorus(np.array([1.0], dtype=np.float32))
    mixer.set_chorus(enabled=False)
    dry = np.array([0.25, -0.5], dtype=np.float32)

    output = mixer._apply_chorus(dry)

    assert output is dry
    assert not mixer._chorus_buffer.any()
    assert mixer._chorus_phase == 0.0


def test_chorus_parameters_are_clamped():
    mixer = Mixer(max_voices=1, sample_rate=1000)
    mixer.set_chorus(enabled=True, rate_hz=9.0, depth_ms=20.0, mix=-0.5)

    assert mixer.chorus_rate_hz == 5.0
    assert mixer.chorus_depth_ms == 10.0
    assert mixer.chorus_mix == 0.0


def test_gui_preset_round_trips_chorus_settings():
    window = MainWindow()
    try:
        window.chorus_enabled_selector.setCurrentIndex(
            window.chorus_enabled_selector.findData(True)
        )
        window.chorus_rate_slider.setValue(23)
        window.chorus_depth_slider.setValue(45)
        window.chorus_mix_slider.setValue(70)
        state = window._collect_preset_state()

        window.chorus_enabled_selector.setCurrentIndex(
            window.chorus_enabled_selector.findData(False)
        )
        window.chorus_rate_slider.setValue(10)
        window._apply_preset_state(state)

        assert state['chorus'] == {
            'enabled': True,
            'rate_hz': 2.3,
            'depth_ms': 4.5,
            'mix': 0.7,
        }
        assert window.audio_engine.mixer.chorus_enabled is True
        assert window.audio_engine.mixer.chorus_rate_hz == 2.3
        assert window.audio_engine.mixer.chorus_depth_ms == 4.5
        assert window.audio_engine.mixer.chorus_mix == 0.7
    finally:
        window.close()