#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MUSA Software Synthesizer - Main Entry Point

A real-time polyphonic synthesizer with:
- 32-voice polyphony
- 2 active octaves (24 MIDI notes)
- 4 waveform types (sine, square, triangle, sawtooth)
- ADSR envelope shaping
- QWERTY keyboard mapping
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_SITE_PACKAGES = PROJECT_ROOT / "venv" / "Lib" / "site-packages"

if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.hex_grid_window import HexGridWindow
from core.note_mapper import NoteMapper


def main() -> int:
    """
    Create the Qt application and show the main window.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
