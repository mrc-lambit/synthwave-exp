import numpy as np

from audio.reverb import SchroederReverb
from gui.main_window import MainWindow


def test_reverb_produces_finite_decaying_tail_across_blocks():
    reverb = SchroederReverb(sample_rate=8000)
    reverb.set_parameters(enabled=True, decay_seconds=0.3, mix=1.0)
    impulse = np.zeros(128, dtype=np.float32)
    impulse[0] = 1.0
    blocks = [reverb.process(impulse)]
    blocks.extend(
        reverb.process(np.zeros(128, dtype=np.float32)) for _ in range(19)
    )
    output = np.concatenate(blocks)

    assert np.isfinite(output).all()
    assert np.count_nonzero(output) > 100
    early_rms = np.sqrt(np.mean(output[256:512] ** 2))
    late_rms = np.sqrt(np.mean(output[-256:] ** 2))
    assert late_rms < early_rms


def test_reverb_bypass_preserves_input_and_clears_state():
    reverb = SchroederReverb(sample_rate=8000)
    reverb.set_parameters(enabled=True, mix=1.0)
    impulse = np.zeros(64, dtype=np.float32)
    impulse[0] = 1.0
    reverb.process(impulse)

    reverb.set_parameters(enabled=False)
    dry = np.array([0.25, -0.5], dtype=np.float32)
    output = reverb.process(dry)

    assert output is dry
    assert not any(buffer.any() for buffer in reverb._comb_buffers)
    assert not any(buffer.any() for buffer in reverb._allpass_buffers)


def test_reverb_parameters_are_clamped_and_feedback_is_stable():
    reverb = SchroederReverb(sample_rate=8000)
    reverb.set_parameters(enabled=True, decay_seconds=20.0, mix=-0.5)

    assert reverb.decay_seconds == 5.0
    assert reverb.mix == 0.0
    assert np.all(reverb._comb_feedback < 1.0)


def test_zero_mix_keeps_reverb_state_advancing():
    reverb = SchroederReverb(sample_rate=8000)
    reverb.set_parameters(enabled=True, decay_seconds=1.8, mix=0.0)
    impulse = np.zeros(64, dtype=np.float32)
    impulse[0] = 1.0

    output = reverb.process(impulse)

    assert np.array_equal(output, impulse)
    assert any(buffer.any() for buffer in reverb._comb_buffers)


def test_gui_preset_round_trips_reverb_settings():
    window = MainWindow()
    try:
        window.reverb_enabled_selector.setCurrentIndex(
            window.reverb_enabled_selector.findData(True)
        )
        window.reverb_decay_slider.setValue(32)
        window.reverb_mix_slider.setValue(55)
        state = window._collect_preset_state()

        window.reverb_enabled_selector.setCurrentIndex(
            window.reverb_enabled_selector.findData(False)
        )
        window.reverb_decay_slider.setValue(10)
        window._apply_preset_state(state)

        assert state['reverb'] == {
            'enabled': True,
            'decay_seconds': 3.2,
            'mix': 0.55,
        }
        assert window.audio_engine.mixer.reverb.enabled is True
        assert window.audio_engine.mixer.reverb.decay_seconds == 3.2
        assert window.audio_engine.mixer.reverb.mix == 0.55
    finally:
        window.close()