#!/usr/bin/env python3
"""Compatibility entry for the workbench's shared replay CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from teleop.gello_cr.replay import main

if __name__ == "__main__":
    raise SystemExit(main())
