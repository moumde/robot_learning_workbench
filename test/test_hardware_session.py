"""Endpoint ownership uses local files, never robot connections."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_robot_session_lock_rejects_other_process_until_release(tmp_path):
    from core.hardware_session import RobotSessionBusyError, RobotSessionLock

    first = RobotSessionLock("192.0.2.1", lock_root=tmp_path)
    contender = RobotSessionLock("192.0.2.1", lock_root=tmp_path)
    first.acquire()
    try:
        with pytest.raises(RobotSessionBusyError):
            contender.acquire()
        program = (
            "from core.hardware_session import RobotSessionLock; "
            f"RobotSessionLock('192.0.2.1', lock_root={str(tmp_path)!r}).acquire()"
        )
        result = subprocess.run(
            [sys.executable, "-c", program], cwd=ROOT, capture_output=True, check=False
        )
        assert result.returncode != 0
        assert b"RobotSessionBusyError" in result.stderr
    finally:
        first.release()
    contender.acquire()
    contender.release()


def test_parent_interface_keeps_lock_when_socket_disconnect_fails(tmp_path, monkeypatch):
    from core.hardware_session import RobotSessionBusyError, RobotSessionLock

    name = "vendor.nrc_interface.nrc_linux_x86_64.nrc_interface"
    sdk = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, sdk)
    spec = importlib.util.spec_from_file_location(
        "vendor.nrc_interface._session_test_interface", ROOT / "vendor/nrc_interface/interface.py"
    )
    interface = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interface)
    guard = RobotSessionLock("192.0.2.2", lock_root=tmp_path)
    robot = interface.CR3Interface("192.0.2.2", session_guard=guard)
    monkeypatch.setattr(robot, "_connect_port", lambda port: port)
    robot.connect()
    contender = RobotSessionLock("192.0.2.2", lock_root=tmp_path)
    sdk.disconnect_robot = lambda fd: (_ for _ in ()).throw(OSError("disconnect failed"))
    with pytest.raises(ExceptionGroup):
        robot.disconnect()
    with pytest.raises(RobotSessionBusyError):
        contender.acquire()
    sdk.disconnect_robot = lambda fd: 0
    robot.disconnect()
    contender.acquire()
    contender.release()


def test_parent_failed_ready_check_cannot_report_a_complete_connection(tmp_path, monkeypatch):
    from core.hardware_session import RobotSessionLock

    name = "vendor.nrc_interface.nrc_linux_x86_64.nrc_interface"
    sdk = ModuleType(name)
    sdk.connect_robot = lambda ip, port: int(port)
    sdk.get_connection_status = lambda fd: 0 if fd == 6001 else -1
    sdk.disconnect_robot = lambda fd: (_ for _ in ()).throw(OSError("disconnect failed"))
    monkeypatch.setitem(sys.modules, name, sdk)
    spec = importlib.util.spec_from_file_location(
        "vendor.nrc_interface._ready_test_interface", ROOT / "vendor/nrc_interface/interface.py"
    )
    interface = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interface)
    robot = interface.CR3Interface(
        "192.0.2.3", connection_timeout=0.001, connection_poll_period=0.001,
        session_guard=RobotSessionLock("192.0.2.3", lock_root=tmp_path),
    )
    try:
        with pytest.raises(interface.NRCConnectionError):
            robot.connect()
        assert not robot.connected
        with pytest.raises(interface.NRCConnectionError, match="partial"):
            robot.connect()
    finally:
        sdk.disconnect_robot = lambda fd: 0
        robot.disconnect()
