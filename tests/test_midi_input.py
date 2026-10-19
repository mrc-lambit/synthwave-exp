from types import SimpleNamespace

import pytest

from core.midi_input import MidiInput
from gui.main_window import MainWindow


def test_midi_input_routes_note_on_and_note_off():
    midi_input = MidiInput()
    events = []
    midi_input.note_on.connect(lambda *args: events.append(("on", *args)))
    midi_input.note_off.connect(lambda *args: events.append(("off", *args)))
    midi_input.control_change.connect(lambda *args: events.append(("cc", *args)))
    midi_input.pitch_bend.connect(lambda *args: events.append(("bend", *args)))
    midi_input.channel_pressure.connect(lambda *args: events.append(("pressure", *args)))
    midi_input.poly_pressure.connect(lambda *args: events.append(("poly", *args)))

    midi_input._handle_message(
        SimpleNamespace(type="note_on", channel=2, note=60, velocity=96)
    )
    midi_input._handle_message(
        SimpleNamespace(type="note_on", channel=2, note=60, velocity=0)
    )
    midi_input._handle_message(
        SimpleNamespace(type="note_off", channel=2, note=61)
    )
    midi_input._handle_message(
        SimpleNamespace(type="control_change", channel=2, control=1, value=80)
    )
    midi_input._handle_message(
        SimpleNamespace(type="pitchwheel", channel=2, pitch=4096)
    )
    midi_input._handle_message(
        SimpleNamespace(type="aftertouch", channel=2, value=90)
    )
    midi_input._handle_message(
        SimpleNamespace(type="polytouch", channel=2, note=61, value=100)
    )

    assert events == [
        ("on", 2, 60, 96),
        ("off", 2, 60),
        ("off", 2, 61),
        ("cc", 2, 1, 80),
        ("bend", 2, 4096),
        ("pressure", 2, 90),
        ("poly", 2, 61, 100),
    ]


def test_main_window_routes_velocity_and_overlapping_note_sources():
    class StubAudioEngine:
        def __init__(self):
            self.note_on_calls = []
            self.note_off_calls = []

        def note_on(self, frequency, amplitude, oscillator_type):
            self.note_on_calls.append((frequency, amplitude, oscillator_type))
            return len(self.note_on_calls)

        def note_off(self, voice_id):
            self.note_off_calls.append(voice_id)

    window = MainWindow()
    real_audio_engine = window.audio_engine
    audio_engine = StubAudioEngine()
    window.audio_engine = audio_engine
    window.is_running = True
    window.status_timer.stop()

    try:
        window._on_midi_note_on(0, 60, 64)
        window._on_midi_note_on(0, 60, 96)
        window._on_note_on(60, window.note_mapper.midi_to_frequency(60))

        assert audio_engine.note_on_calls[0][1] == 64 / 127.0
        assert audio_engine.note_on_calls[1][1] == 96 / 127.0
        assert audio_engine.note_on_calls[2][1] == 0.5
        assert window.active_note_sources[60] == 3

        window._on_midi_note_off(0, 60)
        window._on_midi_note_off(0, 60)
        assert window.active_note_sources[60] == 1
        window._on_note_off(60)

        assert window.active_note_sources == {}
        assert audio_engine.note_off_calls == [1, 2, 3]
    finally:
        window.midi_input.close()
        window.audio_engine = real_audio_engine
        window.is_running = False
        real_audio_engine.stop()
        window.close()


def test_midi_pitch_bend_only_changes_voices_on_its_channel():
    class VoiceStub:
        def __init__(self, frequency, amplitude):
            self.frequency = frequency
            self.amplitude = amplitude

    class AudioEngineStub:
        def __init__(self):
            self.voices = []

        def note_on(self, frequency, amplitude, oscillator_type):
            voice = VoiceStub(frequency, amplitude)
            self.voices.append(voice)
            return voice

        def note_off(self, voice):
            pass

        def set_voice_frequency(self, voice, frequency):
            voice.frequency = frequency

        def set_voice_amplitude(self, voice, amplitude):
            voice.amplitude = amplitude

    window = MainWindow()
    real_audio_engine = window.audio_engine
    audio_engine = AudioEngineStub()
    window.audio_engine = audio_engine
    window.is_running = True
    window.status_timer.stop()

    try:
        window._on_midi_note_on(0, 60, 100)
        window._on_midi_note_on(1, 64, 90)
        channel_zero_voice, channel_one_voice = audio_engine.voices
        channel_one_frequency = channel_one_voice.frequency

        window._on_midi_pitch_bend(0, 8191)
        assert channel_zero_voice.frequency == pytest.approx(
            window.note_mapper.midi_to_frequency(60)
            * 2 ** ((8191 / 8192 * 2) / 12)
        )
        assert channel_one_voice.frequency == channel_one_frequency

        window._on_midi_pitch_bend(0, -8192)
        assert channel_zero_voice.frequency == pytest.approx(
            window.note_mapper.midi_to_frequency(60) * 2 ** (-2 / 12)
        )
    finally:
        window.midi_input.close()
        window.audio_engine = real_audio_engine
        real_audio_engine.stop()
        window.close()


def test_midi_channel_and_poly_aftertouch_scale_only_matching_voices():
    class VoiceStub:
        def __init__(self, frequency, amplitude):
            self.frequency = frequency
            self.amplitude = amplitude

    class AudioEngineStub:
        def __init__(self):
            self.voices = []

        def note_on(self, frequency, amplitude, oscillator_type):
            voice = VoiceStub(frequency, amplitude)
            self.voices.append(voice)
            return voice

        def note_off(self, voice):
            pass

        def set_voice_frequency(self, voice, frequency):
            voice.frequency = frequency

        def set_voice_amplitude(self, voice, amplitude):
            voice.amplitude = amplitude

    window = MainWindow()
    real_audio_engine = window.audio_engine
    audio_engine = AudioEngineStub()
    window.audio_engine = audio_engine
    window.is_running = True
    window.status_timer.stop()

    try:
        window._on_midi_note_on(0, 60, 100)
        window._on_midi_note_on(0, 64, 80)
        window._on_midi_note_on(1, 60, 90)
        first_note, second_note, other_channel = audio_engine.voices
        base_first = first_note.amplitude
        base_second = second_note.amplitude
        base_other = other_channel.amplitude

        window._on_midi_poly_pressure(0, 60, 0)
        assert first_note.amplitude == pytest.approx(base_first * 0.25)
        assert second_note.amplitude == base_second
        assert other_channel.amplitude == base_other

        window._on_midi_channel_pressure(0, 0)
        assert first_note.amplitude == pytest.approx(base_first * 0.25 * 0.25)
        assert second_note.amplitude == pytest.approx(base_second * 0.25)
        assert other_channel.amplitude == base_other

        window._on_midi_poly_pressure(0, 60, 127)
        assert first_note.amplitude == pytest.approx(base_first * 0.25)
    finally:
        window.midi_input.close()
        window.audio_engine = real_audio_engine
        real_audio_engine.stop()
        window.close()


def test_midi_cc_maps_mod_wheel_volume_and_filter_cutoff():
    class AudioEngineStub:
        def __init__(self):
            self.master_volume = None
            self.lfo_settings = None
            self.filter_settings = None

        def set_master_volume(self, volume):
            self.master_volume = volume

        def set_lfo_parameters(self, frequency, depth, target):
            self.lfo_settings = (frequency, depth, target)

        def set_filter(self, kind, cutoff, resonance):
            self.filter_settings = (kind, cutoff, resonance)

    window = MainWindow()
    real_audio_engine = window.audio_engine
    audio_engine = AudioEngineStub()
    window.audio_engine = audio_engine
    window.is_running = False
    window.status_timer.stop()

    try:
        window._on_midi_control_change(0, 1, 64)
        assert window.lfo_xy_pad.depth == 50
        assert audio_engine.lfo_settings == (0.0, 0.5, "pitch")

        window._on_midi_control_change(0, 7, 100)
        assert audio_engine.master_volume == pytest.approx(100 / 127)
        assert window.volume_slider.value() == 79

        window._on_midi_control_change(0, 74, 127)
        assert window.cutoff_slider.value() == 20000
        assert audio_engine.filter_settings == ("lowpass", 20000.0, 0.0)
    finally:
        window.midi_input.close()
        window.audio_engine = real_audio_engine
        real_audio_engine.stop()
        window.close()