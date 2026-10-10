from types import SimpleNamespace

from core.midi_input import MidiInput
from gui.main_window import MainWindow


def test_midi_input_routes_note_on_and_note_off():
    midi_input = MidiInput()
    events = []
    midi_input.note_on.connect(lambda *args: events.append(("on", *args)))
    midi_input.note_off.connect(lambda *args: events.append(("off", *args)))

    midi_input._handle_message(
        SimpleNamespace(type="note_on", channel=2, note=60, velocity=96)
    )
    midi_input._handle_message(
        SimpleNamespace(type="note_on", channel=2, note=60, velocity=0)
    )
    midi_input._handle_message(
        SimpleNamespace(type="note_off", channel=2, note=61)
    )

    assert events == [
        ("on", 2, 60, 96),
        ("off", 2, 60),
        ("off", 2, 61),
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
        real_audio_engine.stop()