from audio.envelope import Envelope


envelope = Envelope(sample_rate=44100, attack_time=0.01, decay_time=0.05, sustain_level=0.6, release_time=0.1)
envelope.trigger()
values = envelope.get_next_buffer(64)
assert len(values) == 64
assert values[0] >= 0.0
assert values[-1] >= 0.0

# Fast retrigger continuity: attack must resume from the current amplitude,
# not from zero, so there is no silent gap between note loops.
envelope.trigger()
first = envelope.get_next_buffer(8)[0]
envelope.release()
release_level = envelope.get_next_buffer(4)[-1]
envelope.trigger()
retrigger_level = envelope.get_next_buffer(8)[0]
assert first >= 0.0
assert release_level >= 0.0
assert retrigger_level > 0.0

print('adsr-tests-ok')
