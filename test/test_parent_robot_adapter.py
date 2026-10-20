"""Parent robot adapter regressions use an in-memory SDK, never hardware."""
import math
from types import SimpleNamespace

import pytest


class Sdk:
    VectorDouble = staticmethod(lambda size=None: [] if size is None else [0.0] * size)
    MoveCmd = SimpleNamespace
    PosType_data = 99

    def __init__(self):
        self.connected = set()
        self.opened = []
        self.closed = []
        self.targets = []
        self.moves = []
        self.stop_count = 0
        self.state = 1
        self.mode = 0
        self.callback = None
        self.disconnect_fails = False
        self.position = [10.0, -20.0, 30.0, 40.0, -50.0, 60.0, 7.5]

    def connect_robot(self, ip, port):
        fd = 10 + len(self.opened)
        self.opened.append((ip, port))
        self.connected.add(fd)
        return fd

    def disconnect_robot(self, fd):
        if self.disconnect_fails:
            raise OSError('disconnect failed')
        self.closed.append(fd)
        self.connected.discard(fd)
        return 0

    def get_connection_status(self, fd):
        return 0 if fd in self.connected else -2

    def get_servo_state_robot(self, fd, robot_num, output):
        return 0, self.state

    def get_current_mode_robot(self, fd, robot_num, output):
        return 0, self.mode

    def set_current_mode_robot(self, fd, robot_num, mode):
        self.mode = mode
        return 0

    def set_servo_state_robot(self, fd, robot_num, state):
        self.state = state
        return 0

    def set_servo_poweron_robot(self, fd, robot_num):
        self.state = 3
        return 0

    def get_current_position(self, fd, coord, output):
        output.extend(self.position if coord == 0 else [400, -100, 250, 0.1, 0.2, 0.3, 7.5])
        return 0

    def set_receive_error_or_warnning_message_callback(self, fd, callback):
        self.callback = callback
        return 0

    def enable_servo_position_motion_control(self, fd, enabled):
        return 0

    def open_servoJ(self, fd, vmax, amax, jmax):
        return 0

    def set_servoJ_pos(self, fd, target):
        self.targets.append((fd, list(target)))
        return 0

    def stop_servoJ(self, fd):
        self.stop_count += 1
        return 0

    def queue_motion_stop_not_power_off(self, fd):
        self.stop_count += 1
        return 0

    def robot_movej(self, fd, command):
        self.moves.append((fd, command))
        return 0


class Guard:
    def __init__(self):
        self.acquires = 0
        self.releases = 0

    def acquire(self):
        self.acquires += 1

    def release(self):
        self.releases += 1


def test_parent_adapter_delegates_reads_and_servo_preserving_external_axis(monkeypatch):
    from core.hardware.cr3a import Cr3aConfig, Cr3aDevice
    from vendor.nrc_interface.interface import CR3Interface

    sdk, guard = Sdk(), Guard()
    device = Cr3aDevice(Cr3aConfig(ip='simulation.invalid', robot_num=2), api=sdk, session_guard=guard)
    assert isinstance(device.backend, CR3Interface)
    assert not sdk.opened
    snapshot = device.connect(timeout=0.1)
    assert snapshot.joints.positions_rad == pytest.approx([math.radians(v) for v in sdk.position[:6]])
    session = device.session
    assert session.backend is device.backend
    assert session.lock is device.backend._lock
    calls = []
    for name in ('get_joint_positions', 'get_tcp_pose', 'send_joint_positions'):
        method = getattr(device.backend, name)
        def call(*args, _method=method, _name=name, **kwargs):
            calls.append(_name)
            return _method(*args, **kwargs)
        monkeypatch.setattr(device.backend, name, call)
    try:
        assert session.joint_position() == pytest.approx(sdk.position)
        assert session.tcp_position()[-1] == 7.5
        device.power_on(timeout=0.1)
        device.start_joint_servo()
        session.send_servoj(sdk.position)
        assert sdk.targets[-1][1] == pytest.approx(sdk.position)
        assert calls == ['get_joint_positions', 'get_tcp_pose', 'send_joint_positions']
        assert session.command_fd == device.command_fd == device.backend.command_fd
        assert session.servo_fd == device.servo_fd == device.backend.servo_fd
        assert len(sdk.opened) == 2
        sdk.connected.clear()
        assert not device.connected
    finally:
        device.close()
    assert guard.acquires == guard.releases == 1


def test_parent_adapter_home_movej_uses_shared_command_channel():
    from core.hardware.cr3a import Cr3aConfig, Cr3aDevice

    sdk, guard = Sdk(), Guard()
    device = Cr3aDevice(Cr3aConfig(ip='simulation.invalid'), api=sdk, session_guard=guard)
    try:
        device.connect(timeout=0.1)
        device.power_on(timeout=0.1)
        device.start_joint_servo()
        device.session.movej(sdk.position, 10, 20, 20)
        fd, command = sdk.moves[-1]
        assert fd == device.backend.command_fd
        assert command.targetPosValue == pytest.approx(sdk.position)
        assert not device.backend.servo_active
    finally:
        device.close()


def test_parent_adapter_retains_endpoint_guard_until_disconnect_succeeds():
    from core.hardware.cr3a import Cr3aConfig, Cr3aDevice

    sdk, guard = Sdk(), Guard()
    device = Cr3aDevice(Cr3aConfig(ip='simulation.invalid'), api=sdk, session_guard=guard)
    device.connect(timeout=0.1)
    sdk.disconnect_fails = True
    with pytest.raises(ExceptionGroup):
        device.close()
    assert guard.acquires == 1 and guard.releases == 0
    assert device.command_fd > 0 and device.servo_fd > 0
    sdk.disconnect_fails = False
    device.close()
    assert guard.releases == 1


def test_partial_close_cannot_report_connected_even_if_sdk_accepts_missing_fd():
    from core.hardware.cr3a import Cr3aConfig, Cr3aDevice
    sdk, guard = Sdk(), Guard()
    device = Cr3aDevice(Cr3aConfig(ip="simulation.invalid"), api=sdk, session_guard=guard)
    device.connect(timeout=0.1)
    original_disconnect = sdk.disconnect_robot
    command_fd = device.command_fd
    def partial_disconnect(fd):
        if fd == command_fd:
            raise OSError("command channel cleanup pending")
        return original_disconnect(fd)
    sdk.disconnect_robot = partial_disconnect
    try:
        with pytest.raises(ExceptionGroup):
            device.close()
        assert device.command_fd > 0 and device.servo_fd == -1
        sdk.get_connection_status = lambda fd: 0
        assert not device.backend.connected
        assert not device.connected
        assert guard.releases == 0
    finally:
        sdk.disconnect_robot = original_disconnect
        device.close()
    assert guard.releases == 1
