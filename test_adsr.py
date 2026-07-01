from audio.envelope import Envelope

envelope = Envelope(sample_rate=44100, attack_time=0.01, decay_time=0.05, sustain_level=0.6, release_time=0.1)
envelope.trigger()
values = envelope.get_next_buffer(64)
assert len(values) == 64
assert values[0] >= 0.0
assert values[-1] >= 0.0
print('adsr-tests-ok')
