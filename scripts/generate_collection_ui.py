"""Regenerate the parent Qt Designer collection UI bindings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from teleop.gello_cr.ui.generate_ui import main

if __name__ == "__main__":
    main()
