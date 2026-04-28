#!/usr/bin/env python3
"""
Rogius TUI Launcher

Simple entry point to run the Rogius TUI.
Usage: python run-tui.py
"""

import sys
from pathlib import Path

# Ensure the tui module can be imported
sys.path.insert(0, str(Path(__file__).parent))

from tui import main

if __name__ == "__main__":
    main()
