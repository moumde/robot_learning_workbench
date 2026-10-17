
from __future__ import annotations

from pathlib import Path

UI_ROOT = Path(__file__).resolve().parents[2] / "src/gello_cr/ui"


def _source(name: str) -> str:
    return (UI_ROOT / name).read_text(encoding="utf-8")


def test_pyside_window_has_no_vendor_or_runtime_imports() -> None:
    source = _source("main_window.py")

    forbidden = (
        "nrc_interface",
        "teleop_runtime",
        "lerobot_recorder",
        "gello_cr.devices",
        "LinkerHand",
        "pyrealsense",
    )
    for token in forbidden:
        assert token not in source


def test_window_submits_commands_through_command_port() -> None:
    source = _source("main_window.py")

    assert "self._command_port.submit(" in source
    assert "ApplicationService" not in source
    assert ".dispatch(" not in source


def test_window_polls_presenter_with_qtimer() -> None:
    source = _source("main_window.py")

    assert "QTimer" in source
    assert "self._presenter.poll()" in source
    assert "refresh_from_presenter" in source


def test_window_exposes_stop_episode_command() -> None:
    source = _source("pages/collection.py")

    assert "Command.STOP_EPISODE" in source
    assert "episode_stop_button" in source


def test_preview_explicitly_contains_no_hardware_backend() -> None:
    source = (UI_ROOT.parents[2] / "examples/preview_ui.py").read_text(encoding="utf-8")

    assert "ApplicationService()" in source
    assert "No Hardware" in source
    for token in (
        "Cr3aDevice",
        "NrcRobot",
        "TeleopEngine",
        "RecordingSession",
        "GelloDevice",
        "O6Device",
        "RealSense",
    ):
        assert token not in source
