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


window = MainWindow()
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

print('harmonic-mode-tests-ok')
