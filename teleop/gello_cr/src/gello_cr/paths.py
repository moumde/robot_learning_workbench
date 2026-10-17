"""Resolve the enclosing workbench while retaining standalone test layouts."""

from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2]


def workbench_root(start: str | Path = APPLICATION_ROOT) -> Path:
    root = Path(start).expanduser().resolve()
    for candidate in (root, *root.parents):
        if (candidate / "config/hardware.py").is_file() and (
            candidate / "vendor/nrc_interface"
        ).is_dir():
            return candidate
    return root
