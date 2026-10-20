"""Compatibility entry for the parent Qt Designer generator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from hmi.collection.generate_ui import main
if __name__ == "__main__":
    main()
