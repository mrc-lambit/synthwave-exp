import wave

import numpy as np
import pytest

from audio.mixer import Mixer
from audio.voice import Voice
from gui.main_window import MainWindow


def _write_periodic_wav(path, sample_rate=8000):
    positions = np.arange(2048)
    samples = (np.sin(2 * np.pi * positions / 64) * 24000).astype('<i2')
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())


def test_unison_at_zero_detune_preserves_the_original_level():
    single = Voice(sample_rate=48000, oscillator_type='sawtooth')
    stacked = Voice(sample_rate=48000, oscillator_type='sawtooth')
    stacked.set_unison_parameters(voices=5, detune_cents=0)
    single.note_on(440, 0.5)
    stacked.note_on(440, 0.5)

    assert np.allclose(single.generate(512), stacked.generate(512))


def test_unison_detune_spreads_oscillator_frequencies_symmetrically():
    voice = Voice(sample_rate=48000)
    voice.set_unison_parameters(voices=3, detune_cents=12)
    voice.note_on(440, 0.5)
    voice.generate(480)

    offsets = np.array([-12, 0, 12])
    expected_phases = (440 * 2 ** (offsets / 1200) * 480 / 48000) % 1
    actual_phases = [oscillator.phase for oscillator in voice.unison_oscillators]
    assert actual_phases == pytest.approx(expected_phases)


def test_adding_unison_oscillators_keeps_zero_detune_phase_aligned():
    voice = Voice(sample_rate=48000)
    voice.note_on(440, 0.5)
    voice.generate(113)
    voice.set_unison_parameters(voices=5, detune_cents=0)

    phases = [oscillator.phase for oscillator in voice.unison_oscillators]
    assert phases == pytest.approx([phases[0]] * 5)


def test_wav_unison_at_zero_detune_preserves_the_original_output(tmp_path):
    sample_path = tmp_path / 'periodic.wav'
    _write_periodic_wav(sample_path)
    single = Voice(sample_rate=8000)
    stacked = Voice(sample_rate=8000)
    single.load_sample(str(sample_path), root_frequency=440)
    stacked.load_sample(str(sample_path), root_frequency=440)
    stacked.set_unison_parameters(voices=5, detune_cents=0)
    single.note_on(440, 0.5)
    stacked.note_on(440, 0.5)

    assert np.allclose(single.generate(512), stacked.generate(512))


def test_wav_unison_detune_uses_independent_playback_rates(tmp_path):
    sample_path = tmp_path / 'periodic.wav'
    _write_periodic_wav(sample_path)
    voice = Voice(sample_rate=8000)
    voice.load_sample(str(sample_path), root_frequency=440)
    voice.set_unison_parameters(voices=3, detune_cents=24)
    voice.note_on(440, 0.5)
    voice.generate(256)

    offsets = np.array([-24, 0, 24])
    expected_positions = (
        256 * 2 ** (offsets / 1200)
    ) % len(voice.sample)
    assert voice._unison_sample_positions == pytest.approx(expected_positions)
    assert voice.sample_position == pytest.approx(expected_positions[0])


def test_mixer_applies_unison_to_active_and_new_voices():
    mixer = Mixer(max_voices=2, sample_rate=8000)
    active_voice = mixer.note_on(440)

    mixer.set_unison_parameters(voices=4, detune_cents=18)
    next_voice = mixer.note_on(660)

    assert active_voice.unison_voices == 4
    assert active_voice.detune_cents == 18
    assert next_voice.unison_voices == 4
    assert next_voice.detune_cents == 18


def test_midi_sample_voice_inherits_unison_settings(tmp_path):
    sample_path = tmp_path / 'periodic.wav'
    _write_periodic_wav(sample_path)
    mixer = Mixer(max_voices=1, sample_rate=8000)
    mixer.load_sample(str(sample_path), root_frequency=440)
    mixer.set_unison_parameters(voices=3, detune_cents=24)

    voice = mixer.note_on(440, oscillator_type='sample')
    voice.generate(256)

    expected_positions = (
        256 * 2 ** (np.array([-24, 0, 24]) / 1200)
    ) % len(voice.sample)
    assert voice._unison_sample_positions == pytest.approx(expected_positions)


def test_additive_and_fm_engines_generate_distinct_timbres():
    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.note_on(440, 0.5)
    waveform = voice.generate(1024)

    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_synthesis_mode('additive')
    voice.set_synthesis_parameters(
        additive_partials=5,
        additive_tilt_db_per_octave=0,
    )
    voice.note_on(440, 0.5)
    additive = voice.generate(1024)

    voice = Voice(sample_rate=48000, oscillator_type='sine')
    voice.set_synthesis_mode('fm')
    voice.set_synthesis_parameters(fm_ratio=2.0, fm_index=4.0)
    voice.note_on(440, 0.5)
    fm = voice.generate(1024)

    assert not np.allclose(waveform, additive)
    assert not np.allclose(waveform, fm)
    assert np.isfinite(additive).all()
    assert np.isfinite(fm).all()


def test_live_synthesis_settings_update_active_and_new_voices():
    mixer = Mixer(max_voices=2, sample_rate=8000)
    active_voice = mixer.note_on(440)
    mixer.set_synthesis_mode('fm')
    mixer.set_synthesis_parameters(
        additive_partials=12,
        additive_tilt_db_per_octave=9,
        fm_ratio=3.5,
        fm_index=5.0,
    )
    next_voice = mixer.note_on(660)

    for voice in (active_voice, next_voice):
        assert voice.synthesis_mode == 'fm'
        assert voice.additive_partials == 12
        assert voice.additive_tilt_db_per_octave == 9
        assert voice.fm_ratio == 3.5
        assert voice.fm_index == 5.0


def test_unison_settings_round_trip_in_gui_presets():
    window = MainWindow()
    try:
        window.unison_voices.setValue(5)
        window.detune_cents.setValue(23)
        window.synthesis_mode_selector.setCurrentText('fm')
        window.additive_partials.setValue(12)
        window.additive_tilt.setValue(9)
        window.fm_ratio.setValue(3.5)
        window.fm_index.setValue(5.0)
        state = window._collect_preset_state()

        window.unison_voices.setValue(1)
        window.detune_cents.setValue(0)
        window.synthesis_mode_selector.setCurrentText('waveform')
        window.additive_partials.setValue(8)
        window.additive_tilt.setValue(6)
        window.fm_ratio.setValue(2)
        window.fm_index.setValue(2)
        window._apply_preset_state(state)

        assert window.unison_voices.value() == 5
        assert window.detune_cents.value() == 23
        assert window.audio_engine.mixer.voice_settings['unison_voices'] == 5
        assert window.audio_engine.mixer.voice_settings['detune_cents'] == 23
        assert window.synthesis_mode_selector.currentText() == 'fm'
        assert window.audio_engine.mixer.voice_settings['synthesis_mode'] == 'fm'
        assert window.additive_partials.value() == 12
        assert window.additive_tilt.value() == 9
        assert window.fm_ratio.value() == 3.5
        assert window.fm_index.value() == 5.0

        window._apply_preset_state({'waveform': 'sine'})
        assert window.unison_voices.value() == 5
        assert window.detune_cents.value() == 23
        assert window.synthesis_mode_selector.currentText() == 'waveform'
    finally:
        window.close()
