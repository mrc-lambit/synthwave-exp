import json
import tempfile
from pathlib import Path

import pytest

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
        'distortion': {'effect': 'fuzz', 'drive': 0.65, 'mix': 0.8},
    }

    manager.save_preset('test-preset', state)
    loaded = manager.load_preset('test-preset')

    assert loaded['oscillator_type'] == 'triangle'
    assert loaded['filter']['kind'] == 'bandpass'
    assert loaded['lfo']['depth'] == 0.25
    assert loaded['distortion'] == {'effect': 'fuzz', 'drive': 0.65, 'mix': 0.8}
    assert manager.get_available_presets() == ['test-preset']


def test_multi_sound_preset_round_trip_omits_empty_sources(tmp_path):
    manager = PresetManager(preset_directory=str(tmp_path))
    state = {
        "name": "multi",
        "multi_sound": {
            "group_count": 3,
            "groups": [
                {"octave": 3, "sample_path": "kick.wav", "sample_root_midi": 48},
                {"octave": 4, "waveform": "triangle", "sample_path": None},
                {"octave": 5, "sample_path": None, "waveform": None},
            ],
        },
    }

    path = manager.save_preset("multi", state)
    serialized = json.loads(path.read_text(encoding="utf-8"))
    loaded = manager.load_preset("multi")

    assert serialized["multi_sound"]["groups"] == [
        {"octave": 3, "sample_path": "kick.wav", "sample_root_midi": 48},
        {"octave": 4, "waveform": "triangle"},
        {"octave": 5},
    ]
    assert loaded["multi_sound"] == serialized["multi_sound"]


def test_silent_multi_sound_config_defaults_to_first_octaves():
    assert PresetManager.create_multi_sound_config(2) == {
        "group_count": 2,
        "groups": [{"octave": 3}, {"octave": 4}],
    }


def test_legacy_preset_without_multi_sound_remains_unchanged(tmp_path):
    manager = PresetManager(preset_directory=str(tmp_path))
    state = {"waveform": "sine", "sample_path": "legacy.wav"}
    manager.save_preset("legacy", state)

    assert manager.load_preset("legacy") == state


def test_multi_sound_preset_rejects_invalid_group_count(tmp_path):
    manager = PresetManager(preset_directory=str(tmp_path))
    with pytest.raises(ValueError, match="group_count"):
        manager.save_preset(
            "invalid",
            {"multi_sound": {"group_count": 5, "groups": []}},
        )
