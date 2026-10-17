from core.chord_engine import ChordEngine, ChordType, HarmonicMode
from gui.main_window import MainWindow

engine = ChordEngine()

single_notes = engine.get_notes_for_mode(60, HarmonicMode.SINGLE)
assert single_notes == [60]

dyad_notes = engine.get_notes_for_mode(60, HarmonicMode.DYAD, ChordType.THIRD_MAJOR)
assert dyad_notes == [60, 64]

minor_dyad_notes = engine.get_notes_for_mode(60, HarmonicMode.DYAD, ChordType.THIRD_MINOR)
assert minor_dyad_notes == [60, 63]

triad_notes = engine.get_notes_for_mode(60, HarmonicMode.TRIAD, ChordType.MAJOR)
assert triad_notes == [60, 64, 67]

minor_triad_notes = engine.get_notes_for_mode(60, HarmonicMode.TRIAD, ChordType.MINOR)
assert minor_triad_notes == [60, 63, 67]


class StubAudioEngine:
    def __init__(self):
        self.note_ids = []
        self.note_off_calls = []

    def note_on(self, frequency, amplitude, oscillator_type):
        voice_id = len(self.note_ids) + 1
        self.note_ids.append(voice_id)
        return voice_id

    def note_off(self, voice_id):
        self.note_off_calls.append(voice_id)


def test_main_window_routes_harmonic_voices():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine = StubAudioEngine()
        window.harmonic_mode = HarmonicMode.TRIAD
        window.chord_type = ChordType.MAJOR

        window._on_note_on(60, 261.63)
        assert 60 in window.midi_note_voices
        assert len(window.midi_note_voices[60]) == 3

        window._on_note_off(60)
        assert window.midi_note_voices == {}
        assert window.audio_engine.note_off_calls == [1, 2, 3]
    finally:
        window.close()


def test_mono_legato_reuses_voice_and_returns_to_last_held_note():
    window = MainWindow()
    try:
        window.is_running = True
        window.audio_engine.is_running = True
        window.voice_mode_selector.setCurrentText("mono")
        window.legato_checkbox.setChecked(True)

        window._on_note_on(60, window.note_mapper.midi_to_frequency(60))
        voice = window.midi_note_voices[60][0]
        window.audio_engine.mixer.mix(64)
        envelope_stage = voice.envelope.current_stage
        envelope_counter = voice.envelope.sample_counter

        window._on_note_on(64, window.note_mapper.midi_to_frequency(64))
        assert window.midi_note_voices[64][0] is voice
        assert window.audio_engine.mixer.active_voices == [voice]
        assert voice.frequency == window.note_mapper.midi_to_frequency(64)
        assert voice.envelope.current_stage == envelope_stage
        assert voice.envelope.sample_counter == envelope_counter

        window._on_note_off(64)
        assert voice.frequency == window.note_mapper.midi_to_frequency(60)
        assert voice.is_active

        window._on_note_off(60)
        assert not voice.is_active
    finally:
        window.is_running = False
        window.audio_engine.is_running = False
        window.close()
