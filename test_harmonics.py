from core.chord_engine import ChordEngine, HarmonicMode

engine = ChordEngine()

single_notes = engine.get_notes_for_mode(60, HarmonicMode.SINGLE)
assert single_notes == [60]

dyad_notes = engine.get_notes_for_mode(60, HarmonicMode.DYAD)
assert dyad_notes == [60, 64]

triad_notes = engine.get_notes_for_mode(60, HarmonicMode.TRIAD)
assert triad_notes == [60, 64, 67]

print('harmonic-mode-tests-ok')
