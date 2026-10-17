"""Physical GELLO samples stay distinct from adapter polls, without a serial port."""

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from gello_cr.devices.gello import GelloDevice
from tests.v2.test_gello_device import _config


@pytest.fixture
def bundled_gello(monkeypatch):
    root = Path(__file__).resolve().parents[4] / "vendor/gello/gello"
    for suffix, attributes in {
        "group_sync_read": {"GroupSyncRead": object},
        "group_sync_write": {"GroupSyncWrite": object},
        "packet_handler": {"PacketHandler": object},
        "port_handler": {"PortHandler": object},
        "robotis_def": {
            name: 0
            for name in ("COMM_SUCCESS", "DXL_HIBYTE", "DXL_HIWORD", "DXL_LOBYTE", "DXL_LOWORD")
        },
    }.items():
        module = ModuleType("dynamixel_sdk." + suffix)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, module.__name__, module)

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, root / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    driver_module = load("gello_test_driver", "dynamixel/driver.py")
    protocol_module = load("gello_test_robot_protocol", "robots/robot.py")
    monkeypatch.setitem(sys.modules, "gello.robots.robot", protocol_module)
    robot_module = load("gello_test_robot", "robots/dynamixel.py")
    return driver_module, robot_module


def driver_without_serial(module, monkeypatch):
    monkeypatch.setattr(module.DynamixelDriver, "_initialize_with_retries", lambda self: True)
    return module.DynamixelDriver((1, 2, 3, 4, 5, 6, 7))


def test_bus_failures_preserve_last_successful_sample_timestamp(bundled_gello, monkeypatch):
    module, _ = bundled_gello
    driver = driver_without_serial(module, monkeypatch)
    ticks = [10.0]
    calls = []

    def transaction():
        calls.append(ticks[0])
        if len(calls) == 1:
            return module.COMM_SUCCESS
        if len(calls) == 3:
            driver._stop_thread.set()
        return -1

    driver._groupSyncRead = SimpleNamespace(
        txRxPacket=transaction,
        isAvailable=lambda *args: True,
        getData=lambda *args: 1024,
    )
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(
            monotonic=lambda: ticks[0],
            sleep=lambda duration: ticks.__setitem__(0, ticks[0] + duration),
        ),
    )
    driver._read_joint_states()
    positions, sampled_at = driver.get_joint_sample()

    assert sampled_at == calls[0]
    assert sampled_at < calls[-1]
    assert positions == pytest.approx((np.pi / 2,) * 7)
    positions[0] = 100
    assert driver.get_joint_sample()[0][0] == pytest.approx(np.pi / 2)


def test_reader_exception_reaches_sample_consumer(bundled_gello, monkeypatch):
    module, _ = bundled_gello
    driver = driver_without_serial(module, monkeypatch)
    driver._groupSyncRead = SimpleNamespace(
        txRxPacket=lambda: module.COMM_SUCCESS,
        isAvailable=lambda *args: False,
    )
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: 10, sleep=lambda _: None))
    driver._read_joint_states()

    with pytest.raises(RuntimeError, match="Failed to get velocity"):
        driver.get_joint_sample()


def test_robot_sample_keeps_calibration_and_physical_timestamp(bundled_gello):
    _, module = bundled_gello
    robot = object.__new__(module.DynamixelRobot)
    robot._driver = SimpleNamespace(get_joint_sample=lambda: (np.array([1.0] * 6 + [2.0]), 123.5))
    robot._joint_ids = tuple(range(1, 8))
    robot._joint_offsets = np.array([0.1] * 6 + [0.0])
    robot._joint_signs = np.array([-1.0] + [1.0] * 6)
    robot.gripper_open_close = (1.0, 3.0)
    robot._last_pos = None
    robot._alpha = 0.99

    positions, sampled_at = robot.get_joint_state_sample()

    assert sampled_at == 123.5
    assert positions == pytest.approx((-0.9,) + (0.9,) * 5 + (0.5,))


def test_cached_driver_sample_expires_in_device_instead_of_being_restamped():
    sampled_at = time.monotonic()
    robot = SimpleNamespace(
        get_joint_state=lambda: (0.0,) * 7,
        get_joint_state_sample=lambda: ((0.0,) * 7, sampled_at),
        close=lambda: None,
    )
    device = GelloDevice(_config(), robot_factory=lambda **_: robot)
    try:
        first = device.connect(timeout=0.5)
        assert first.timestamp == sampled_at
        deadline = time.monotonic() + 0.8
        while not device.error and time.monotonic() < deadline:
            time.sleep(0.005)
        assert "sample" in device.error.lower()
        assert not device.feedback_fresh()
        assert device.latest().timestamp == sampled_at
    finally:
        device.close()


def test_legacy_external_factory_is_rejected_before_device_constructor(monkeypatch):
    constructed = []

    class LegacyRobot:
        def __init__(self, **kwargs):
            constructed.append(True)

        def close(self):
            pass

    external = ModuleType("gello.robots.dynamixel")
    external.DynamixelRobot = LegacyRobot
    monkeypatch.setitem(sys.modules, external.__name__, external)
    device = GelloDevice(_config())

    with pytest.raises(RuntimeError, match="get_joint_state_sample"):
        device.connect(timeout=0.1)

    assert not constructed
