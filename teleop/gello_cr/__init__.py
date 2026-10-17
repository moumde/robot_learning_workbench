"""Expose the imported GELLO package without importing hardware drivers."""

import sys
from pathlib import Path

_SOURCE_ROOT = str(Path(__file__).resolve().parent / "src")
if _SOURCE_ROOT not in sys.path:
    sys.path.insert(0, _SOURCE_ROOT)
