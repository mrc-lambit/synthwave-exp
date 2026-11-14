# -*- coding: utf-8 -*-
"""Preset persistence utilities for the synthesizer."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class PresetManager:
    """Save and load synth presets as JSON files."""

    WAVEFORMS = {"sine", "square", "triangle", "sawtooth"}

    def __init__(self, preset_directory: Optional[str] = None) -> None:
        self.preset_directory = Path(preset_directory or "presets")
        self.preset_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create_multi_sound_config(cls, group_count: int) -> Dict[str, Any]:
        """Create silent consecutive octave groups, ready for source assignment."""
        if type(group_count) is not int or not 2 <= group_count <= 4:
            raise ValueError("Multi-sound presets require 2 to 4 groups")
        return {
            "group_count": group_count,
            "groups": [{"octave": octave} for octave in range(3, 3 + group_count)],
        }

    @classmethod
    def normalize_multi_sound_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a multi-sound layout and omit unset source fields."""
        if not isinstance(config, dict):
            raise ValueError("multi_sound must be an object")
        group_count = config.get("group_count")
        if type(group_count) is not int or not 2 <= group_count <= 4:
            raise ValueError("multi_sound.group_count must be between 2 and 4")
        groups = config.get("groups")
        if not isinstance(groups, list) or len(groups) != group_count:
            raise ValueError("multi_sound.groups must match group_count")

        normalized_groups = []
        allowed_keys = {"octave", "sample_path", "sample_root_midi", "waveform"}
        for index, group in enumerate(groups):
            if not isinstance(group, dict) or set(group) - allowed_keys:
                raise ValueError(f"Invalid multi_sound group at index {index}")
            octave = group.get("octave")
            if type(octave) is not int or octave != 3 + index:
                raise ValueError("Groups must be consecutive octaves starting at 3")

            sample_path = group.get("sample_path")
            waveform = group.get("waveform")
            if sample_path is not None and not isinstance(sample_path, str):
                raise ValueError("sample_path must be a string or null")
            sample_path = sample_path.strip() if sample_path else None
            if waveform is not None and not isinstance(waveform, str):
                raise ValueError("waveform must be a string or null")
            waveform = waveform.strip() if waveform else None
            if waveform is not None and waveform not in cls.WAVEFORMS:
                raise ValueError(f"Unsupported waveform: {waveform}")
            if sample_path and waveform:
                raise ValueError("A group can use a sample or waveform, not both")

            normalized = {"octave": octave}
            if sample_path:
                normalized["sample_path"] = sample_path
                root_midi = group.get("sample_root_midi")
                if root_midi is not None:
                    if type(root_midi) is not int or not 0 <= root_midi <= 127:
                        raise ValueError("sample_root_midi must be between 0 and 127")
                    normalized["sample_root_midi"] = root_midi
            elif waveform:
                normalized["waveform"] = waveform
            normalized_groups.append(normalized)

        return {"group_count": group_count, "groups": normalized_groups}

    def save_preset(self, name: str, state: Dict[str, Any]) -> Path:
        preset_path = self.preset_directory / f"{name}.json"
        state = dict(state)
        if "multi_sound" in state:
            state["multi_sound"] = self.normalize_multi_sound_config(
                state["multi_sound"]
            )
        with preset_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return preset_path

    def load_preset(self, name: str) -> Dict[str, Any]:
        preset_path = self.preset_directory / f"{name}.json"
        with preset_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if "multi_sound" in state:
            state["multi_sound"] = self.normalize_multi_sound_config(
                state["multi_sound"]
            )
        return state

    def get_available_presets(self) -> List[str]:
        return sorted(path.stem for path in self.preset_directory.glob("*.json"))
