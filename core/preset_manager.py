# -*- coding: utf-8 -*-
"""Preset persistence utilities for the synthesizer."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class PresetManager:
    """Save and load synth presets as JSON files."""

    def __init__(self, preset_directory: Optional[str] = None) -> None:
        self.preset_directory = Path(preset_directory or "presets")
        self.preset_directory.mkdir(parents=True, exist_ok=True)

    def save_preset(self, name: str, state: Dict[str, Any]) -> Path:
        preset_path = self.preset_directory / f"{name}.json"
        with preset_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return preset_path

    def load_preset(self, name: str) -> Dict[str, Any]:
        preset_path = self.preset_directory / f"{name}.json"
        with preset_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def get_available_presets(self) -> List[str]:
        return sorted(path.stem for path in self.preset_directory.glob("*.json"))
