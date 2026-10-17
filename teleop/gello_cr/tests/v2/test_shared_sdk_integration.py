"""Shared SDK boundaries exercised without native imports or device opens."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from gello_cr.bootstrap.runtime_factory import (
    ConcreteRuntimeFactory,
    Cr3aLifecycle,
    RuntimeFactoryPaths,
)
from gello_cr.devices.cr3a import Cr3aConfig, Cr3aDevice
from gello_cr.devices.o6 import O6Config, O6Device
from tests.v2.test_concrete_runtime_factory import CFG, Store, constructors
from tests.v2.test_cr3a_device import FakeNrcApi

WORKBENCH = Path(__file__).resolve().parents[4]


def test_cr3a_preserves_each_servoj_axis_from_hardware_profile():
    api = FakeNrcApi()
    device = Cr3aDevice(
        Cr3aConfig(
            ip="unused",
            servoj_vmax=[11, 12, 13, 14, 15, 16, 17],
            servoj_amax=[21, 22, 23, 24, 25, 26, 27],
            servoj_jmax=[31, 32, 33, 34, 35, 36, 37],
        ),
        api=api,
    )
    try:
        device.connect(timeout=0.2)
        device.start_joint_servo()
        assert ("open_servoJ", 22, (11, 12, 13, 14, 15, 16, 17),
                (21, 22, 23, 24, 25, 26, 27), (31, 32, 33, 34, 35, 36, 37)) in api.calls
    finally:
        device.close()


def test_config_runtime_and_camera_factory_accept_shared_hardware_values(tmp_path, monkeypatch):
    from gello_cr.app.config_store import TeleopConfigStore
    from gello_cr.app.runtime import TeleopRuntime

    store = TeleopConfigStore(tmp_path / "workbench.json")
    store.update_runtime({"robot": {"servoj_vmax": [11, 12, 13, 14, 15, 16, 17]}})
    runtime = TeleopRuntime(store, SimpleNamespace(), SimpleNamespace())
    assert tuple(runtime.trajectory_player.servo_profile[0]) == (11, 12, 13, 14, 15, 16, 17)
    assert tuple(runtime.point_motion.player.servo_profile[0]) == (11, 12, 13, 14, 15, 16, 17)

    monkeypatch.setitem(CFG["robot"], "servoj_vmax", [11, 12, 13, 14, 15, 16, 17])
    monkeypatch.setitem(CFG["dataset"], "camera_width", 320)
    monkeypatch.setitem(CFG["dataset"], "camera_height", 240)
    monkeypatch.setitem(CFG["dataset"], "camera_fps", 15)
    paths = RuntimeFactoryPaths.from_repo(tmp_path)
    lifecycle = Cr3aLifecycle(store=Store(paths.config_path), teleop_engine=None, paths=paths)
    assert tuple(lifecycle._robot_config().servoj_vmax) == (11, 12, 13, 14, 15, 16, 17)
    built = ConcreteRuntimeFactory(paths, constructors=constructors()).build()
    camera_config = built.camera_devices["base"].args[0]
    assert (camera_config.width, camera_config.height, camera_config.fps) == (320, 240, 15)


def test_shared_o6_load_does_not_replace_workbench_core(monkeypatch):
    core = ModuleType("core")
    core.workbench_marker = object()
    monkeypatch.setitem(sys.modules, "core", core)
    pymodbus = ModuleType("pymodbus.client")
    pymodbus.ModbusSerialClient = object
    monkeypatch.setitem(sys.modules, "pymodbus.client", pymodbus)
    before = sys.path.copy()
    device = O6Device(O6Config(port="unused", sdk_root=str(
        WORKBENCH / "vendor/actuator/linkerhand-python-sdk/LinkerHand"
    )))

    factory = device._load_hand_factory()

    assert factory.__name__ == "LinkerHandO6RS485"
    assert factory.__module__ != "core.rs485.linker_hand_o6_rs485"
    assert sys.modules["core"] is core
    assert sys.path == before


def test_default_nrc_reuses_parent_qualified_module(monkeypatch):
    sdk = WORKBENCH / "vendor/nrc_interface/nrc_linux_x86_64"
    name = "vendor.nrc_interface.nrc_linux_x86_64.nrc_interface"
    fake = ModuleType(name)
    fake.__file__ = str(sdk / "nrc_interface.py")
    monkeypatch.setitem(sys.modules, name, fake)
    monkeypatch.delenv("NRC_SDK_ROOT", raising=False)
    assert Cr3aDevice(Cr3aConfig(ip="unused"))._load_api() is fake


def test_paths_find_shared_workbench_when_launched_from_teleop():
    paths = RuntimeFactoryPaths.from_repo(WORKBENCH / "teleop/gello_cr")
    assert paths.config_path == WORKBENCH / "config/teleop/gello_cr.json"
    assert paths.nrc_sdk_root == WORKBENCH / "vendor/nrc_interface/nrc_linux_x86_64"
    assert paths.linker_hand_sdk_root == (
        WORKBENCH / "vendor/actuator/linkerhand-python-sdk/LinkerHand"
    )


@pytest.mark.parametrize("limit", [[1] * 6, [1] * 8, [1, 2, 3, 4, 5, 6, float("nan")]])
def test_servoj_invalid_axis_limits_fail_before_sdk_writes(limit):
    from gello_cr.devices.nrc_robot import NrcRobotSession
    api = FakeNrcApi()
    session = NrcRobotSession(api, 11, 22, robot_num=1, motion_mode="servoj")
    with pytest.raises(ValueError):
        session.open_servoj(limit, 20, 30)
    assert not api.calls


def test_failed_connection_cleanup_keeps_device_and_lock_for_retry(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(WORKBENCH))
    from core.hardware_session import RobotSessionBusyError, RobotSessionLock

    api = FakeNrcApi()
    api.next_fds = [11, -1]
    original_disconnect = api.disconnect_robot
    api.disconnect_robot = lambda fd: (_ for _ in ()).throw(OSError("busy disconnect"))
    guard = RobotSessionLock("192.0.2.8", lock_root=tmp_path)
    device = Cr3aDevice(Cr3aConfig(ip="192.0.2.8"), api=api, session_guard=guard)
    life = Cr3aLifecycle(
        store=Store(tmp_path / "config.json"), teleop_engine=SimpleNamespace(),
        paths=RuntimeFactoryPaths.from_repo(tmp_path),
        device_constructor=lambda *args, **kwargs: device,
    )
    contender = RobotSessionLock("192.0.2.8", lock_root=tmp_path)
    try:
        with pytest.raises(ConnectionError):
            life.connect()
        assert life.device is device
        assert device.command_fd == 11
        with pytest.raises(RobotSessionBusyError):
            contender.acquire()
    finally:
        api.disconnect_robot = original_disconnect
        life.disconnect()
    contender.acquire()
    contender.release()


def test_session_guard_refuses_connection_before_sdk_loading(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(WORKBENCH))
    from core.hardware_session import RobotSessionBusyError, RobotSessionLock

    guard = RobotSessionLock("192.0.2.9", lock_root=tmp_path)
    guard.acquire()
    device = Cr3aDevice(
        Cr3aConfig(ip="192.0.2.9"),
        session_guard=RobotSessionLock("192.0.2.9", lock_root=tmp_path),
        api_loader=lambda: (_ for _ in ()).throw(AssertionError("SDK loaded before ownership")),
    )
    try:
        with pytest.raises(RobotSessionBusyError):
            device.connect()
    finally:
        guard.release()


def test_failed_initial_snapshot_never_becomes_a_successful_connection(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(WORKBENCH))
    from core.hardware_session import RobotSessionLock

    api = FakeNrcApi()
    original_disconnect = api.disconnect_robot
    api.disconnect_robot = lambda fd: (_ for _ in ()).throw(OSError("busy disconnect"))
    api.get_current_position = lambda *args: (_ for _ in ()).throw(RuntimeError("bad feedback"))
    device = Cr3aDevice(
        Cr3aConfig(ip="192.0.2.10"), api=api,
        session_guard=RobotSessionLock("192.0.2.10", lock_root=tmp_path),
    )
    try:
        with pytest.raises(RuntimeError, match="bad feedback"):
            device.connect(timeout=0.2)
        assert not device.connected
        assert device.command_fd == 11
        assert device.servo_fd == 22
    finally:
        api.disconnect_robot = original_disconnect
        device.close()
