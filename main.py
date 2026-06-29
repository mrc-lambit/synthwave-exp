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

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


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
