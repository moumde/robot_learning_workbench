
from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

from gello_cr.bootstrap.runtime_factory import Cr3aLifecycle, RuntimeFactoryPaths


class Session:
    def __init__(self):
        self.state = 1
        self.calls = []
    def stop_motion(self): self.calls.append('stop_motion')
    def power_on(self):
        self.calls.append('power_on')
        self.state = 3
        return 'on'
    def power_off(self):
        self.calls.append('power_off')
        self.state = 1
        return 'off'
    def servo_state(self): return self.state


class Device:
    instances = []
    def __init__(self, config, event_callback=None):
        self.config = config
        self.event_callback = event_callback
        self.connected = False
        self.session = Session()
        self.closed = 0
        Device.instances.append(self)
    def connect(self, timeout=10.0):
        self.connected = True
        return object()
    def close(self):
        self.closed += 1
        self.connected = False


class Store:
    data = {
        'robot': {
            'ip': '192.168.1.245', 'command_port': 6001,
            'servo_port': 7000, 'robot_num': 1,
            'movej_velocity': 10.0, 'movej_acc': 20.0,
            'movej_dec': 20.0, 'movej_period_s': 0.1,
            'movej_low_latency': False,
            'servoj_vmax': 80.0, 'servoj_amax': 200.0,
            'servoj_jmax': 150.0,
        }
    }

    def deployment_data(self):
        return self.data


class Engine:
    def __init__(self):
        self.attached = []
        self.detached = []
        self.estops = []
        self.acks = 0
    def attach_robot(self, session): self.attached.append(session)
    def detach_robot(self, session, reason, *, expected=False):
        self.detached.append((session, reason)); return True
    def emergency_stop(self, reason): self.estops.append(reason)
    def stop_motion(self, reason): self.estops.append(("controlled", reason))
    def acknowledge_fault(self): self.acks += 1


_lifecycles = []


@pytest.fixture(autouse=True)
def close_lifecycles():
    yield
    for life in _lifecycles:
        life.disconnect()
    _lifecycles.clear()


def lifecycle(tmp_path):
    life = Cr3aLifecycle(
        store=Store(),
        teleop_engine=Engine(),
        paths=RuntimeFactoryPaths(
            repo_root=tmp_path,
            config_path=tmp_path/'config.json',
            linker_hand_sdk_root=tmp_path/'hand',
            nrc_sdk_root=None,
        ),
        device_constructor=Device,
    )
    _lifecycles.append(life)
    return life


def test_lifecycle_construction_is_disconnected(tmp_path) -> None:
    Device.instances.clear()
    life = lifecycle(tmp_path)
    assert life.device is None
    assert life.session is None
    assert Device.instances == []


def test_connect_creates_device_only_on_explicit_callback(tmp_path) -> None:
    Device.instances.clear()
    life = lifecycle(tmp_path)
    session = life.connect()

    assert len(Device.instances) == 1
    assert life.session is session
    assert life._teleop_engine.attached == [session]


def test_power_on_and_off_use_existing_session(tmp_path) -> None:
    life = lifecycle(tmp_path)
    session = life.connect()

    assert life.power_on() == 'on'
    assert session.state == 3
    assert life.power_off() == 'off'
    assert session.state == 1
    assert life._teleop_engine.estops == [("controlled", '下使能前停止当前动作')]
    life.disconnect()


def test_reset_from_connected_acknowledges_without_power_on(
    tmp_path,
) -> None:
    life = lifecycle(tmp_path)
    session = life.connect()

    # Simulate a connected/non-enabled controller state.
    session.state = 2

    life.reset_fault()

    # RESET from a connection that was never explicitly POWER_ON must
    # never enable the robot.
    assert session.state == 2
    assert 'power_on' not in session.calls

    # Runtime fault acknowledgement still occurs.
    assert life._teleop_engine.acks == 1

    # RESET must never resume teleoperation.
    assert not hasattr(
        life._teleop_engine,
        'start_follow_called',
    )


def test_disconnect_detaches_then_closes_and_clears_refs(tmp_path) -> None:
    life = lifecycle(tmp_path)
    session = life.connect()
    device = life.device

    assert life.disconnect()
    assert life._teleop_engine.detached
    assert device.closed >= 1
    assert life.device is None
    assert life.session is None


def test_status_reads_cache_without_sdk_io_and_commands_update_it(tmp_path):
    life = lifecycle(tmp_path)
    assert life.status_snapshot()["servo_state"] == "unknown"
    life.connect()
    try:
        assert life.status_snapshot()["connected"]
        assert life.status_snapshot()["servo_state"] == "off"
        life.power_on()
        life.stop_feedback()
        original = life.session.servo_state
        life.session.servo_state = lambda: (_ for _ in ()).throw(AssertionError("GUI SDK I/O"))
        cached = life.status_snapshot()
        assert cached["servo_state"] == "on"
        assert cached["desired_enabled"]
        assert cached["sampled_at"] is not None
        life.session.servo_state = original
        life.power_off()
        assert life.status_snapshot()["servo_state"] == "off"
    finally:
        life.disconnect()
    assert not life.status_snapshot()["connected"]
    assert life.status_snapshot()["servo_state"] == "unknown"


def test_feedback_tracks_hardware_and_stops_before_disconnect(tmp_path):
    life = lifecycle(tmp_path)
    life.connect()
    worker = life._feedback_thread
    assert worker.is_alive()
    life.session.state = 3
    deadline = time.monotonic() + 1
    while life.status_snapshot()["servo_state"] != "on" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert life.status_snapshot()["servo_state"] == "on"
    assert life.connect() is life.session
    assert life._feedback_thread is worker
    life.disconnect()
    assert not worker.is_alive()


def test_blocked_feedback_does_not_block_cache_and_disconnect_is_retryable(tmp_path):
    life = lifecycle(tmp_path)
    life.connect()
    entered, release = threading.Event(), threading.Event()
    original = life.session.servo_state

    def blocked():
        entered.set()
        assert release.wait(2)
        return original()

    life.session.servo_state = blocked
    assert entered.wait(1)
    start = time.monotonic()
    assert life.status_snapshot()["servo_state"] == "off"
    with pytest.raises(TimeoutError, match="反馈"):
        life.disconnect()
    assert time.monotonic() - start < 1
    assert life.session is not None
    release.set()
    life.disconnect()


def test_alarm_feedback_cannot_be_displayed_as_enabled(tmp_path):
    life = lifecycle(tmp_path)
    life.connect()
    life.session.state = 2
    deadline = time.monotonic() + 1
    while life.status_snapshot()["servo_state"] == "off" and time.monotonic() < deadline:
        time.sleep(0.01)
    status = life.status_snapshot()
    assert status["servo_state"] == "error"
    assert "2" in status["error"]
