"""Behavior tests for the GELLO startup dependency preflight."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from teleop.gello_cr.ui import dependencies


def result(code, stderr=""):
    return subprocess.CompletedProcess([], code, stdout="", stderr=stderr)


def test_available_sdk_needs_no_install(monkeypatch):
    commands = []
    monkeypatch.setattr(
        dependencies.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or result(0),
    )
    monkeypatch.setattr(
        dependencies.shutil, "which", lambda name: pytest.fail("installer lookup was not needed")
    )

    dependencies.ensure_dynamixel_sdk()

    assert len(commands) == 1
    assert commands[0][0] == sys.executable
    assert "-c" in commands[0]


@pytest.mark.parametrize("uv", ["/test/uv", None], ids=["uv", "pip"])
def test_missing_sdk_is_installed_into_running_python_and_rechecked(monkeypatch, uv):
    commands = []
    outcomes = iter([result(42), result(0), result(0)])
    monkeypatch.setattr(
        dependencies.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or next(outcomes),
    )
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: uv)

    dependencies.ensure_dynamixel_sdk()

    assert len(commands) == 3
    assert commands[0][0] == commands[2][0] == sys.executable
    expected = (
        [uv, "pip", "install", "--python", sys.executable, "dynamixel-sdk"]
        if uv
        else [sys.executable, "-m", "pip", "install", "dynamixel-sdk"]
    )
    assert commands[1] == expected


def test_install_failure_stops_with_actionable_error(monkeypatch):
    commands = []
    outcomes = iter([result(42), result(1, "network unavailable")])
    monkeypatch.setattr(
        dependencies.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or next(outcomes),
    )
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError) as exc:
        dependencies.ensure_dynamixel_sdk()

    assert "network unavailable" in str(exc.value)
    assert sys.executable in str(exc.value)
    assert len(commands) == 2


def test_installer_timeout_stops_with_actionable_error(monkeypatch):
    def run(command, **kwargs):
        if "-c" in command:
            return result(42)
        assert kwargs["stdin"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(dependencies.subprocess, "run", run)
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as exc:
        dependencies.ensure_dynamixel_sdk()
    assert sys.executable in str(exc.value)
    assert "setup_teleop_env.sh" in str(exc.value)


def test_broken_sdk_does_not_get_treated_as_missing(monkeypatch):
    commands = []
    monkeypatch.setattr(
        dependencies.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or result(1, "missing serial"),
    )
    monkeypatch.setattr(
        dependencies.shutil,
        "which",
        lambda name: pytest.fail("broken installation must not trigger blind installation"),
    )

    with pytest.raises(RuntimeError) as exc:
        dependencies.ensure_dynamixel_sdk()

    assert "missing serial" in str(exc.value)
    assert len(commands) == 1


def test_successful_installer_must_still_pass_import_check(monkeypatch):
    outcomes = iter([result(42), result(0), result(42, "still missing")])
    monkeypatch.setattr(dependencies.subprocess, "run", lambda command, **kwargs: next(outcomes))
    monkeypatch.setattr(dependencies.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError):
        dependencies.ensure_dynamixel_sdk()


def _offline_operator(master):
    from teleop.gello_cr.core.state_machine import WorkflowState

    closed = []
    operator = SimpleNamespace(
        runtime=SimpleNamespace(
            store=SimpleNamespace(
                data={
                    "logging": {"level": "INFO"},
                    "master": {"type": master},
                }
            )
        ),
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        close=lambda: closed.append(True),
    )
    return operator, closed


def test_check_only_does_not_install_sdk(tmp_path, monkeypatch):
    from teleop.gello_cr.ui import __main__ as entrypoint

    operator, closed = _offline_operator("gello")
    monkeypatch.setattr(
        entrypoint, "ensure_dynamixel_sdk", lambda: pytest.fail("check-only must remain read-only")
    )

    assert (
        entrypoint.main(
            ["--repo-root", str(tmp_path), "--check-only"], application_factory=lambda _: operator
        )
        == 0
    )
    assert closed == [True]


def test_failed_gello_preflight_closes_offline_application_before_gui(tmp_path, monkeypatch):
    from teleop.gello_cr.ui import __main__ as entrypoint

    operator, closed = _offline_operator("gello")

    def fail_preflight():
        raise RuntimeError("SDK setup failed")

    monkeypatch.setattr(entrypoint, "ensure_dynamixel_sdk", fail_preflight)

    with pytest.raises(RuntimeError, match="SDK setup failed"):
        entrypoint.main(["--repo-root", str(tmp_path)], application_factory=lambda _: operator)
    assert closed == [True]


@pytest.mark.parametrize("master", ["roarm", "inverse3"])
def test_other_masters_do_not_install_sdk_before_gui(tmp_path, monkeypatch, master):
    import builtins

    from teleop.gello_cr.ui import __main__ as entrypoint

    operator, _ = _offline_operator(master)
    monkeypatch.setattr(
        entrypoint,
        "ensure_dynamixel_sdk",
        lambda: pytest.fail("non-GELLO master should not install SDK"),
    )
    original_import = builtins.__import__

    def stop_before_gui(name, *args, **kwargs):
        if name == "PySide6.QtWidgets":
            raise RuntimeError("GUI boundary reached")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", stop_before_gui)

    with pytest.raises(RuntimeError, match="GUI boundary reached"):
        entrypoint.main(["--repo-root", str(tmp_path)], application_factory=lambda _: operator)


def test_import_probe_distinguishes_missing_broken_and_complete_sdk(tmp_path, monkeypatch):
    """Run the real probe against isolated fake packages, without any hardware."""
    import os

    real_run = subprocess.run
    commands = []
    monkeypatch.setattr(
        dependencies.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or result(0),
    )
    dependencies.ensure_dynamixel_sdk()
    probe = commands[0]
    code = probe[probe.index("-c") + 1]
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}

    def check():
        return real_run(
            [sys.executable, "-S", "-c", code], env=env, capture_output=True, text=True
        ).returncode

    assert check() == 42
    package = tmp_path / "dynamixel_sdk"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    symbols = {
        "group_sync_read": "GroupSyncRead",
        "group_sync_write": "GroupSyncWrite",
        "packet_handler": "PacketHandler",
        "port_handler": "PortHandler",
        "robotis_def": "COMM_SUCCESS DXL_HIBYTE DXL_HIWORD DXL_LOBYTE DXL_LOWORD",
    }
    for module_name, names in symbols.items():
        contents = "\n".join(f"{name} = None" for name in names.split())
        (package / f"{module_name}.py").write_text(contents, encoding="utf-8")
    assert check() == 0
    (package / "group_sync_write.py").unlink()
    broken = check()
    assert broken != 0 and broken != 42
