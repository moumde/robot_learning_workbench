"""Locate source files by their canonical repository-relative paths."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def implementation_path(relative):
    return REPO_ROOT / relative
