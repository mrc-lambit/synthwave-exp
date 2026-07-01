from core.chord_engine import ChordEngine, ChordType, HarmonicMode

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

print('harmonic-mode-tests-ok')
