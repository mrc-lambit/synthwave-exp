import numpy as np
import pytest

from audio.mixer import Mixer
from gui.main_window import MainWindow


def test_delay_echo_and_feedback_continue_across_audio_blocks():
    mixer = Mixer(max_voices=1, sample_rate=100)
    mixer.set_delay(enabled=True, time_ms=20, feedback=0.5, mix=1.0)

    first_block = mixer._apply_delay(np.array([1, 0, 0], dtype=np.float32))
    second_block = mixer._apply_delay(np.zeros(3, dtype=np.float32))

    assert np.allclose(first_block, [0, 0, 1])
    assert np.allclose(second_block, [0, 0.5, 0])


def test_delay_mix_blends_dry_and_wet_signal():
    mixer = Mixer(max_voices=1, sample_rate=100)
    mixer.set_delay(enabled=True, time_ms=10, feedback=0.0, mix=0.5)

    output = mixer._apply_delay(np.array([1, 0], dtype=np.float32))

    assert np.allclose(output, [0.5, 0.5])


def test_delay_bypass_preserves_input_and_clears_old_echoes():
    mixer = Mixer(max_voices=1, sample_rate=100)
    mixer.set_delay(enabled=True, time_ms=10, feedback=0.5, mix=1.0)
    mixer._apply_delay(np.array([1], dtype=np.float32))

    mixer.set_delay(enabled=False)
    dry = np.array([0.25, -0.5], dtype=np.float32)
    output = mixer._apply_delay(dry)

    assert output is dry
    assert not mixer._delay_buffer.any()


def test_delay_parameters_are_clamped():
    mixer = Mixer(max_voices=1, sample_rate=100)
    mixer.set_delay(enabled=True, time_ms=5000, feedback=1.5, mix=-0.2)

    assert mixer.delay_time_ms == 2000
    assert mixer.delay_feedback == 0.95
    assert mixer.delay_mix == 0.0


def test_gui_preset_round_trips_delay_settings():
    window = MainWindow()
    try:
        window.delay_enabled_selector.setCurrentIndex(
            window.delay_enabled_selector.findData(True)
        )
        window.delay_time_slider.setValue(375)
        window.delay_feedback_slider.setValue(70)
        window.delay_mix_slider.setValue(40)
        state = window._collect_preset_state()

        window.delay_enabled_selector.setCurrentIndex(
            window.delay_enabled_selector.findData(False)
        )
        window.delay_time_slider.setValue(100)
        window._apply_preset_state(state)

        assert state['delay'] == {
            'enabled': True,
            'time_ms': 375,
            'feedback': 0.7,
            'mix': 0.4,
        }
        assert window.audio_engine.mixer.delay_enabled is True
        assert window.audio_engine.mixer.delay_time_ms == 375
        assert window.audio_engine.mixer.delay_feedback == 0.7
        assert window.audio_engine.mixer.delay_mix == 0.4
    finally:
        window.close()