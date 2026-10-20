"""Compatibility imports for the parent Robot Learning Workbench packages."""
from pathlib import Path
import sys

for _root in Path(__file__).resolve().parents:
    if (_root / "core/workbench").is_dir() and (_root / "config/hardware.py").is_file():
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        break
from core.workbench import __version__
__all__ = ["__version__"]
