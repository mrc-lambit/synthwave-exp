import json
import tempfile
from pathlib import Path

from core.preset_manager import PresetManager


def test_preset_manager_round_trip(tmp_path):
    manager = PresetManager(preset_directory=str(tmp_path))
    state = {
        'name': 'test-preset',
        'oscillator_type': 'triangle',
        'master_volume': 0.65,
        'harmonic_mode': 'single',
        'chord_type': 'major',
        'adsr': {'attack': 0.02, 'decay': 0.15, 'sustain': 0.8, 'release': 0.4},
        'filter': {'kind': 'bandpass', 'cutoff': 1800.0, 'resonance': 0.2},
        'lfo': {'target': 'pitch', 'frequency': 3.5, 'depth': 0.25},
    }

    manager.save_preset('test-preset', state)
    loaded = manager.load_preset('test-preset')

    assert loaded['oscillator_type'] == 'triangle'
    assert loaded['filter']['kind'] == 'bandpass'
    assert loaded['lfo']['depth'] == 0.25
    assert manager.get_available_presets() == ['test-preset']
