"""Behavioral acceptance with injected devices; no SDK/serial/network I/O."""
import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest

from teleop.gello_cr.app import ApplicationService, RuntimeCommandBindings, RuntimeLifecycleCallbacks
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.bootstrap.operator_app import OperatorApplication
from teleop.gello_cr.bootstrap.runtime_factory import Cr3aLifecycle, RuntimeFactoryPaths, ConcreteRuntime
from teleop.gello_cr.hardware.cr3a import Cr3aDevice
from teleop.gello_cr.ui.command_port import AsyncApplicationCommandPort, CommandAlreadyPending, CommandRequest
from teleop.gello_cr.tests.v2.test_cr3a_device import FakeNrcApi
from teleop.gello_cr.tests.v2.test_cr3a_concrete_lifecycle import Store, Engine
from teleop.gello_cr.tests.v2.test_recording_episode_recorder import _recorder
from teleop.gello_cr.tests.v2.test_recording_frame import _sample


def test_connect_power_reset_with_real_adapters_and_fake_sdk(tmp_path):
    api = FakeNrcApi()
    api.state = 1
    engine = Engine()
    life = Cr3aLifecycle(
        store=Store(), teleop_engine=engine, paths=RuntimeFactoryPaths.from_repo(tmp_path),
        device_constructor=lambda cfg, **kw: Cr3aDevice(cfg, api=api, **kw),
    )
    service = ApplicationService()
    RuntimeCommandBindings(service, teleop_engine=engine, recorder=None, lifecycle=life.callbacks()).install()
    assert service.state is WorkflowState.OFFLINE
    assert not api.connect_calls
    service.dispatch(Command.CONNECT)
    assert service.state is WorkflowState.CONNECTED
    assert [port for _, port in api.connect_calls] == ['6001', '7000']
    assert len(life.session.joint_position()) == 7
    assert len(life.session.tcp_position()) == 7
    assert life.session.servo_state() == 1
    assert not life.session.servoj_open
    assert not any('poweron' in str(c) or 'open_servo' in str(c) for c in api.calls)
    service.dispatch(Command.POWER_ON)
    assert service.state is WorkflowState.ROBOT_ENABLED
    assert life.session.servo_state() == 3
    assert not life.session.servoj_open
    service.dispatch(Command.POWER_OFF)
    assert service.state is WorkflowState.CONNECTED
    assert life.session.servo_state() == 1
    service.dispatch(Command.DISCONNECT)
    assert service.state is WorkflowState.OFFLINE


@pytest.mark.parametrize(
    ('previous', 'expected'),
    [
        (WorkflowState.CONNECTED, WorkflowState.CONNECTED),
        (WorkflowState.ROBOT_ENABLED, WorkflowState.ROBOT_ENABLED),
        (WorkflowState.TELEOP_RUNNING, WorkflowState.ROBOT_ENABLED),
        (WorkflowState.TELEOP_RUNNING, WorkflowState.ROBOT_ENABLED),
    ],
)
@pytest.mark.parametrize(
    ('stop', 'reset'),
    [
        (Command.EMERGENCY_STOP, Command.RESET_ESTOP),
        (Command.REPORT_FAULT, Command.RESET_FAULT),
    ],
)
def test_reset_restores_safe_recovery_state(
    previous,
    expected,
    stop,
    reset,
):
    service = ApplicationService(
        state_machine=WorkflowStateMachine(previous)
    )
    service.dispatch(stop)

    result = service.dispatch(reset)

    assert result.state is expected


def test_duplicate_command_rejected_while_safety_remains_available():
    started, release, stopped = threading.Event(), threading.Event(), threading.Event()
    def connect(_):
        started.set()
        assert release.wait(2)
    service = ApplicationService(handlers={Command.CONNECT: connect,
        Command.EMERGENCY_STOP: lambda _: stopped.set()})
    port = AsyncApplicationCommandPort(service)
    try:
        port.submit(CommandRequest.create(Command.CONNECT))
        assert started.wait(1)
        with pytest.raises(CommandAlreadyPending):
            port.submit(CommandRequest.create(Command.CONNECT))
        port.submit(CommandRequest.create(Command.EMERGENCY_STOP))
        assert stopped.wait(1)
    finally:
        release.set()
        port.close()


@pytest.mark.parametrize('flag', ['wrist_age_exceeded', 'base_age_exceeded', 'camera_skew_exceeded'])
def test_stale_camera_prevents_episode_before_worker_created(flag):
    recorder = _recorder()
    sample = _sample()
    sample = replace(sample, metadata={'quality': {flag: 1.0}})
    recorder.source = SimpleNamespace(capture=lambda: sample)
    with pytest.raises(RuntimeError, match=flag):
        recorder.start_episode('task', '/unused')
    assert not recorder.snapshot()['session_active']


def test_quality_tracking_warning_does_not_reject_episode_preflight():
    sample = _sample()
    sample = replace(sample, metadata={'quality': {'tracking_error_exceeded': 1.0}})
    _recorder()._validate_frame(sample)


@pytest.mark.parametrize('snapshot', [{'episode_active': True}, {'buffered_frames': 2}])
def test_application_refuses_exit_without_touching_pending_episode(snapshot):
    app = OperatorApplication(runtime=SimpleNamespace(recorder=SimpleNamespace(snapshot=lambda: snapshot)),
                              backend=None, cameras=None, readiness=None, preparation_bindings=None)
    with pytest.raises(RuntimeError, match='Episode'):
        app.close()


def test_application_cleanup_continues_and_retries_only_failed_resources():
    calls = []
    def fail_once():
        calls.append('runtime')
        if calls.count('runtime') == 1:
            raise OSError('disconnect failed')
    backend = SimpleNamespace(
        command_port=SimpleNamespace(pending_commands=(), stop_accepting=lambda: None,
                                     close=lambda **kw: calls.append('commands')),
        bindings=SimpleNamespace(close=lambda **kw: None),
        presenter=SimpleNamespace(close=lambda: calls.append('presenter')))
    runtime = SimpleNamespace(close=fail_once, teleop_engine=SimpleNamespace(shutdown=lambda **kw: None, snapshot=lambda: {}), recorder=SimpleNamespace(
        snapshot=lambda: {}, stop_episode=lambda: None, close=lambda: calls.append('recorder')))
    app = OperatorApplication(runtime, backend, SimpleNamespace(close=lambda: calls.append('cameras')),
                              None, None)
    with pytest.raises(ExceptionGroup):
        app.close()
    assert calls == ['commands', 'cameras', 'runtime', 'recorder']
    app.close()
    assert calls == ['commands', 'cameras', 'runtime', 'recorder', 'runtime', 'presenter']


def test_runtime_cleanup_preserves_devices_after_stop_failure():
    calls = []
    def broken_stop(**kw):
        calls.append('stop')
        raise OSError('stop failed')
    def device(name):
        return SimpleNamespace(close=lambda **kw: calls.append(name))
    runtime = ConcreteRuntime(None, None, device('roarm'), device('inverse3'), device('gello'),
        None, device('o6'), SimpleNamespace(shutdown=broken_stop), None, None, {},
        SimpleNamespace(stop_feedback=lambda: None, shutdown_power=lambda: calls.append('power'),
                        disconnect=lambda: calls.append('disconnect')))
    with pytest.raises(ExceptionGroup):
        runtime.close()
    assert calls == ['stop']


def test_readiness_enforced_through_application_service():
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED))
    ready = {'master_connected': False, 'o6_connected': False,
             'camera_error': 'stale', 'camera_frames_ready': False}
    RuntimeCommandBindings(service, teleop_engine=None, recorder=None,
                           readiness_snapshot=lambda: ready).install()
    with pytest.raises(RuntimeError, match='尚未就绪'):
        service.dispatch(Command.START_TELEOP)
    assert service.state is WorkflowState.ROBOT_ENABLED


def test_pending_episode_blocks_reset_before_power_on():
    service = ApplicationService(state_machine=WorkflowStateMachine(WorkflowState.ESTOP))
    calls = []
    RuntimeCommandBindings(service, teleop_engine=None, recorder=None,
        lifecycle=RuntimeLifecycleCallbacks(reset_estop=lambda: calls.append('power')),
        recording_snapshot=lambda: {'buffered_frames': 3}).install()
    with pytest.raises(RuntimeError, match='Episode'):
        service.dispatch(Command.RESET_ESTOP)
    assert calls == [] and service.state is WorkflowState.ESTOP


def test_cr3a_close_retries_only_failed_socket():
    api = FakeNrcApi()
    from test_cr3a_device import _config
    device = Cr3aDevice(_config(), api=api)
    device.connect()
    failed_fd = device.command_fd
    closed = []
    def disconnect(fd):
        closed.append(fd)
        if fd == failed_fd and closed.count(fd) == 1:
            raise OSError('disconnect failed')
    api.disconnect_robot = disconnect
    with pytest.raises(ExceptionGroup):
        device.close()
    assert closed == [11, 22]
    device.close()
    assert closed == [11, 22, 11]
    device.close()
    assert closed == [11, 22, 11]






def test_reset_from_connected_does_not_power_on_robot(tmp_path):
    api = FakeNrcApi()
    api.state = 1

    engine = Engine()

    life = Cr3aLifecycle(
        store=Store(),
        teleop_engine=engine,
        paths=RuntimeFactoryPaths.from_repo(tmp_path),
        device_constructor=lambda cfg, **kw: Cr3aDevice(
            cfg,
            api=api,
            **kw,
        ),
    )

    service = ApplicationService()

    RuntimeCommandBindings(
        service,
        teleop_engine=engine,
        recorder=None,
        lifecycle=life.callbacks(),
    ).install()

    try:
        service.dispatch(Command.CONNECT)

        assert service.state is WorkflowState.CONNECTED
        assert life.session.servo_state() == 1

        service.dispatch(Command.EMERGENCY_STOP)

        assert service.state is WorkflowState.ESTOP

        service.dispatch(Command.RESET_ESTOP)

        assert service.state is WorkflowState.CONNECTED
        assert life.session.servo_state() == 1
        assert not life.session.servoj_open
    finally:
        life.disconnect()


def test_reset_from_enabled_restores_enable_but_not_follow(tmp_path):
    api = FakeNrcApi()
    api.state = 1

    engine = Engine()

    life = Cr3aLifecycle(
        store=Store(),
        teleop_engine=engine,
        paths=RuntimeFactoryPaths.from_repo(tmp_path),
        device_constructor=lambda cfg, **kw: Cr3aDevice(
            cfg,
            api=api,
            **kw,
        ),
    )

    service = ApplicationService()

    RuntimeCommandBindings(
        service,
        teleop_engine=engine,
        recorder=None,
        lifecycle=life.callbacks(),
    ).install()

    try:
        service.dispatch(Command.CONNECT)
        service.dispatch(Command.POWER_ON)

        assert service.state is WorkflowState.ROBOT_ENABLED
        assert life.session.servo_state() == 3

        service.dispatch(Command.EMERGENCY_STOP)

        # Simulate controller dropping servo power during the safety event.
        api.state = 1

        service.dispatch(Command.RESET_ESTOP)

        assert service.state is WorkflowState.ROBOT_ENABLED
        assert life.session.servo_state() == 3
        assert not life.session.servoj_open
    finally:
        life.disconnect()
