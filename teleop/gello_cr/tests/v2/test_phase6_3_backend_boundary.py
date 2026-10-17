
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = ROOT / "src/gello_cr/ui"


def test_backend_module_has_no_vendor_sdk_imports() -> None:
    source = (UI_ROOT / "backend.py").read_text(encoding="utf-8")

    for token in (
        "nrc_interface",
        "gello_cr.devices",
        "teleop_runtime",
        "lerobot_recorder",
        "pyrealsense",
        "LinkerHand",
    ):
        assert token not in source


def test_backend_compose_does_not_call_connect_power_or_start() -> None:
    source = (UI_ROOT / "backend.py").read_text(encoding="utf-8")

    compose = source.split("def compose(", 1)[1].split(
        "    def close(", 1
    )[0]

    for forbidden in (
        ".connect(",
        ".power_on(",
        ".start_follow(",
        ".start_episode(",
        ".start(",
    ):
        assert forbidden not in compose


def test_session_lazy_imports_main_window() -> None:
    source = (UI_ROOT / "session.py").read_text(encoding="utf-8")

    assert "from .main_window import OperatorMainWindow" in source
    assert "QApplication" not in source


def test_new_ui_still_does_not_import_legacy_qt_entrypoint() -> None:
    for name in ("backend.py", "session.py", "main_window.py"):
        source = (UI_ROOT / name).read_text(encoding="utf-8")
        assert "TEST_INEXBOT" not in source
        assert "PyQt5" not in source
