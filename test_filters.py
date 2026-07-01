import numpy as np
from audio.filter import Filter

samples = np.array([0.0, 0.5, -0.5, 0.25], dtype=np.float32)
lowpass = Filter(kind='lowpass', cutoff=1000.0, resonance=0.5)
output = lowpass.process(samples, sample_rate=44100)
assert output.shape == samples.shape
assert np.isfinite(output).all()
print('filter-tests-ok')
