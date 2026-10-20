"""HOME cancellation drains one operation while its command worker stays alive."""

import threading

import pytest

from core.workbench.app.config_store import TeleopConfigStore
from core.workbench.app.runtime import TeleopRuntime
from core.workbench.app.service import ApplicationService, CommandSuperseded
from core.workbench.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from hmi.collection.command_port import AsyncApplicationCommandPort, CommandRequest
from test.workbench.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


@pytest.fixture
def runtime(tmp_path):
    store = TeleopConfigStore(tmp_path / "workbench.json")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    engine.attach_robot(FakeRobot())
    engine.save_home()
    yield engine
    engine.shutdown()


def home_commands(runtime):
    service = ApplicationService(
        state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED),
        handlers={
            Command.RETURN_HOME: lambda _payload: runtime.return_home(),
            Command.STOP_MOTION: lambda _payload: runtime.stop_motion(),
        },
    )
    errors = []
    port = AsyncApplicationCommandPort(
        service, error_callback=lambda request, exc: errors.append((request.command, exc))
    )
    return service, port, errors


def block_home_feedback(runtime, release):
    entered = threading.Event()
    original = runtime.robot.joint_position

    def joint_position():
        if runtime.robot.movej_targets:
            entered.set()
            assert release.wait(10), "test did not release HOME feedback"
        return original()

    runtime.robot.joint_position = joint_position
    return entered


def test_stop_drains_home_without_waiting_for_persistent_command_worker(runtime):
    entered = block_home_feedback(runtime, runtime._home_stop)
    service, port, errors = home_commands(runtime)
    try:
        port.submit(CommandRequest.create(Command.RETURN_HOME))
        assert entered.wait(1)

        service.dispatch(Command.STOP_MOTION)

        assert runtime.state == "idle"
        assert service.state is WorkflowState.ROBOT_ENABLED
        assert runtime.motion.current_owner is None
        assert port._home_thread.is_alive()
        assert not runtime._home_lock.locked()

        # The same resident worker can run another explicit HOME after STOP.
        runtime.robot.joint_position = lambda: list(runtime.robot.joints)
        port._home_queue.join()
        port.submit(CommandRequest.create(Command.RETURN_HOME))
        port._home_queue.join()
        assert len(runtime.robot.movej_targets) == 2
        assert runtime.state == "idle"
        assert all(isinstance(error, CommandSuperseded) for _, error in errors)
    finally:
        port.close()


def test_shutdown_drains_home_without_waiting_for_persistent_command_worker(runtime):
    entered = block_home_feedback(runtime, runtime._home_stop)
    _service, port, _errors = home_commands(runtime)
    try:
        port.submit(CommandRequest.create(Command.RETURN_HOME))
        assert entered.wait(1)

        runtime.shutdown()

        assert runtime.state == "closed"
        assert runtime.motion.current_owner is None
        assert not runtime._home_lock.locked()
        assert port._home_thread.is_alive()
        assert not runtime.o6.connected
        assert not runtime.roarm.connected
    finally:
        port.close()


@pytest.mark.parametrize("operation", ["stop_motion", "shutdown"])
def test_stuck_home_times_out_and_preserves_devices_until_operation_finishes(runtime, operation):
    release = threading.Event()
    entered = block_home_feedback(runtime, release)
    _service, port, _errors = home_commands(runtime)
    robot = runtime.robot
    try:
        port.submit(CommandRequest.create(Command.RETURN_HOME))
        assert entered.wait(1)

        error_type = ExceptionGroup if operation == "shutdown" else TimeoutError
        with pytest.raises(error_type) as failure:
            getattr(runtime, operation)()
        if operation == "shutdown":
            assert any(isinstance(exc, TimeoutError) for exc in failure.value.exceptions)
        assert runtime._home_lock.locked()
        assert runtime.robot is robot
        assert runtime.o6.connected
        assert runtime.roarm.connected
        assert runtime.motion.current_owner is None

        release.set()
        port._home_queue.join()
        assert not runtime._home_lock.locked()
        getattr(runtime, operation)()
        assert runtime.state == ("closed" if operation == "shutdown" else "idle")
    finally:
        release.set()
        port.close()


def test_shutdown_from_home_operation_does_not_wait_for_itself(runtime):
    original = runtime.robot.servo_state

    def shutdown_during_enable_check():
        runtime.shutdown(close_devices=False)
        return original()

    runtime.robot.servo_state = shutdown_during_enable_check

    with pytest.raises(RuntimeError, match="停止|状态改变"):
        runtime.return_home()

    assert runtime.state == "closed"
    assert runtime.motion.current_owner is None
    assert not runtime._home_lock.locked()
    assert runtime.robot.movej_targets == []
