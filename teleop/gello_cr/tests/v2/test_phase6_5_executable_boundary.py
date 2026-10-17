
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_module_entry_exists_and_has_check_only_mode() -> None:
    source = _source("src/gello_cr/ui/__main__.py")

    assert "--check-only" in source
    assert "build_operator_application" in source
    assert "workflow=" in source


def test_gui_entry_does_not_auto_start_camera_service() -> None:
    source = _source("src/gello_cr/ui/__main__.py")

    assert ".cameras.start(" not in source
    assert ".wrist_camera.connect(" not in source
    assert ".base_camera.connect(" not in source


def test_gui_entry_does_not_auto_connect_or_power_robot() -> None:
    source = _source("src/gello_cr/ui/__main__.py")

    for forbidden in (
        ".dispatch(Command.CONNECT",
        ".dispatch(Command.POWER_ON",
        ".start_follow(",
        ".connect_devices(",
    ):
        assert forbidden not in source


def test_pyside_import_occurs_only_after_check_only_branch() -> None:
    source = _source("src/gello_cr/ui/__main__.py")

    check_index = source.index("if args.check_only:")
    pyside_index = source.index("from PySide6.QtWidgets import QApplication")
    assert check_index < pyside_index


def test_camera_service_uses_pure_roi_transform() -> None:
    source = _source("src/gello_cr/bootstrap/camera_service.py")

    assert "crop_normalized_roi" in source
    assert "pyrealsense2" not in source
    assert "PySide6" not in source
    assert "PyQt5" not in source
