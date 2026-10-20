"""Failures keep their command, reason and traceback in the parent log directory."""

from __future__ import annotations

import logging
import queue
import sys
import threading
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from teleop.gello_cr.app.background import BackgroundJobs
from teleop.gello_cr.app.runtime import TeleopRuntime
from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
from teleop.gello_cr.app.service import ApplicationService
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.schema import IMAGE_KEYS
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.tests.control.test_teleop_dispatch_safety import loop as following_loop  # noqa: F401
from teleop.gello_cr.ui import __main__ as entrypoint


@pytest.fixture(autouse=True)
def restore_logging():
    # Each test owns its file destination and must leave other logger users intact.
    loggers = [logging.getLogger(name) for name in
               ("workbench", "teleop.gello_cr", "cr3_o6_workflow", "cr3_o6_policy_deploy",
                "cr3_o6_trajectory_replay", "cr3_o6_ptp_replay", "vendor")]
    saved = [(logger, list(logger.handlers), logger.level, logger.propagate) for logger in loggers]
    for logger in loggers:
        logger.handlers = []
    yield
    for logger, handlers, level, propagate in saved:
        for handler in logger.handlers[:]:
            if handler not in handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate


def initialize_logging(root):
    operator = SimpleNamespace(
        runtime=SimpleNamespace(store=SimpleNamespace(data={
            "logging": {"level": "INFO"}, "master": {"type": "gello"},
        })),
        backend=SimpleNamespace(service=SimpleNamespace(state=WorkflowState.OFFLINE)),
        cameras=SimpleNamespace(running=False),
        close=lambda: None,
    )
    assert entrypoint.main(["--repo-root", str(root), "--check-only"],
                           application_factory=lambda _: operator) == 0


def read_log(root):
    path = root / "logs" / "teleop.log"
    assert path.is_file(), "normal entry must create the parent logs/teleop.log"
    return path.read_text()


def test_startup_factory_failure_is_logged_before_operator_exists(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    def broken_factory(_root):
        raise OSError("cannot read selected collection profile")

    with pytest.raises(OSError, match="selected collection profile"):
        entrypoint.main(["--repo-root", str(tmp_path), "--check-only"],
                        application_factory=broken_factory)

    text = read_log(tmp_path)
    assert "startup" in text.lower()
    assert "cannot read selected collection profile" in text
    assert "Traceback (most recent call last)" in text
    assert not (elsewhere / "logs").exists()


@pytest.mark.parametrize(("command", "state"), [
    (Command.CONNECT, WorkflowState.OFFLINE),
    (Command.EMERGENCY_STOP, WorkflowState.TELEOP_RUNNING),
    (Command.RETURN_HOME, WorkflowState.ROBOT_ENABLED),
])
def test_command_failure_keeps_command_traceback_and_ui_event(tmp_path, command, state):
    initialize_logging(tmp_path)
    service = ApplicationService(state_machine=WorkflowStateMachine(state=state, recovery_state=state))
    events = []
    service.subscribe(events.append)

    def device_failure(_payload):
        raise RuntimeError("controller rejected operation")

    service.set_handler(command, device_failure)
    with pytest.raises(RuntimeError, match="controller rejected"):
        service.dispatch(command, {"token": "do-not-log-payload"})

    text = read_log(tmp_path)
    assert command.name in text
    assert "controller rejected operation" in text
    assert "Traceback (most recent call last)" in text
    assert "do-not-log-payload" not in text
    assert any("controller rejected operation" in event.message for event in events)


@pytest.mark.parametrize("operation", ["trajectory", "point"])
def test_async_motion_fault_keeps_original_exception_traceback(tmp_path, operation):
    from teleop.gello_cr.app.planning_service import PointMotionService
    from teleop.gello_cr.app.trajectory_service import TrajectoryService

    initialize_logging(tmp_path)
    service = ApplicationService()
    events = []

    def fail_play(*args, **kwargs):
        raise OSError(f"{operation} device link dropped")

    runtime = SimpleNamespace(
        state="replay" if operation == "trajectory" else "point_move", stop_generation=0,
        store=SimpleNamespace(data={
            "robot": {"servoj_vmax": 1, "servoj_amax": 1, "servoj_jmax": 1},
            "replay": {"servoj_period_s": .01, "max_joint_speed_deg_s": 90},
        }),
        motion=SimpleNamespace(), trajectory_source=SimpleNamespace(),
        trajectory_player=SimpleNamespace(play=fail_play),
        _event=lambda level, message, **kw: events.append((level, message)),
    )
    runtime._set_state = lambda state, error="": setattr(runtime, "state", state)
    bindings = RuntimeCommandBindings(service, teleop_engine=runtime, recorder=SimpleNamespace())
    lease = SimpleNamespace(release=lambda **kwargs: None)
    if operation == "trajectory":
        bindings._trajectory_run = 1
        TrajectoryService(runtime)._play_trajectory_worker(
            None, None, lease, 0, lambda error: bindings._trajectory_finished(1, error))
    else:
        bindings._point_run = 1
        point = PointMotionService(runtime)
        point.player = SimpleNamespace(play=fail_play)
        point._run(None, lease, SimpleNamespace(joint_tolerance_rad=.01), 0,
                   lambda error: bindings._point_finished(1, error))
    bindings.close()

    text = read_log(tmp_path)
    assert f"{operation} device link dropped" in text
    assert "REPORT_FAULT" in text
    assert "Traceback (most recent call last)" in text
    assert any(level == "error" for level, message in events)
    assert service.state is WorkflowState.FAULT


def test_background_failure_logs_even_when_completion_consumes_exception(tmp_path):
    initialize_logging(tmp_path)
    jobs = BackgroundJobs()
    observed = []

    def write_dataset():
        raise OSError("dataset volume full")

    thread = jobs.start(write_dataset, lambda value, error: observed.append(error), name="Dataset-Finalize")
    thread.join(1)
    jobs.close()
    assert isinstance(observed[0], OSError)
    text = read_log(tmp_path)
    assert "Dataset-Finalize" in text
    assert "dataset volume full" in text
    assert "Traceback (most recent call last)" in text


def test_recorder_sampling_failure_keeps_traceback_and_error_event(tmp_path):
    initialize_logging(tmp_path)
    events = []

    class FailedWriter:
        def add_frame(self, frame):
            raise OSError("recorder disk disconnected")

    session = RecordingSession(SimpleNamespace(), FailedWriter,
                               event_callback=lambda *event: events.append(event), image_size=(2, 2))
    session._writer = FailedWriter()
    session._recording_mode = "joint"
    frame = CaptureFrame(1.0, (0.0,) * 12, (0.0,) * 12,
                         {key: np.zeros((2, 2, 3), dtype=np.uint8) for key in IMAGE_KEYS},
                         metadata={"recording_mode": "joint"})
    session._record_loop(frame)

    text = read_log(tmp_path)
    assert "recorder" in text.lower()
    assert "recorder disk disconnected" in text
    assert "Traceback (most recent call last)" in text
    assert any(level == "error" and "recorder disk disconnected" in message for level, message in events)
    assert "recorder disk disconnected" in session.snapshot()["error"]


def test_replay_cli_failure_is_logged_and_preserves_console_feedback(tmp_path, capsys):
    from teleop.gello_cr.cli.replay_trajectory import main

    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path / "missing.json"), "--repo-root", str(tmp_path)],
             runtime_factory=lambda paths: None)
    assert stopped.value.code == 1
    assert "Replay failed:" in capsys.readouterr().err
    text = read_log(tmp_path)
    assert "replay" in text.lower()
    assert "missing.json" in text
    assert "Traceback (most recent call last)" in text


def test_replay_wrapper_logs_startup_config_failure(tmp_path):
    from teleop.gello_cr.cli.replay import main

    config = tmp_path / "bad.json"
    config.write_text("{not valid json")
    # Executing must reach the real configuration loader, but fail before any device is created.
    trajectory = tmp_path / "legacy.json"
    trajectory.write_text('{"version":3,"frames":[{"t":0,"robot_joints_deg":[0,0,0,0,0,0,0]}]}')
    with pytest.raises((SystemExit, ValueError, RuntimeError)):
        main([str(trajectory), "--execute", "--arm-only", "--repo-root", str(tmp_path),
              "--config", str(config)])
    text = read_log(tmp_path)
    assert "replay" in text.lower()
    assert "Traceback (most recent call last)" in text


def test_parent_workflow_startup_failure_is_logged(tmp_path, monkeypatch):
    from core.openpi.cr3_o6 import run_workflow as workflow

    monkeypatch.setattr(workflow, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_workflow", "--confirm-motion", "--plan-json", "{"])
    assert workflow.main() == 1
    text = read_log(tmp_path)
    assert "workflow" in text.lower()
    assert "JSONDecodeError" in text
    assert "Traceback (most recent call last)" in text


def test_parent_workflow_execution_failure_is_logged_without_cli(tmp_path, monkeypatch):
    from core.openpi.cr3_o6 import run_workflow as workflow

    monkeypatch.setattr(workflow, "REPO_ROOT", tmp_path)

    class BrokenRobot:
        def connect(self):
            raise OSError("workflow controller connection refused")

        def disconnect(self):
            pass

    hardware = SimpleNamespace(
        create_nrc_interface=BrokenRobot, nrc=SimpleNamespace(ip="offline-test"), source="test",
        hand=SimpleNamespace(model="O6", joint_count=6, transport="rs485"),
    )
    monkeypatch.setattr(workflow, "load_hardware_config", lambda _: hardware)
    # Empty tasks exercise hardware startup without needing any trajectory/policy files.
    assert workflow.run_workflow(tasks=[], config_path=None, policy_host="localhost", policy_port=8000) == 1
    text = read_log(tmp_path)
    assert "workflow controller connection refused" in text
    assert "Traceback (most recent call last)" in text


def test_repeated_initialization_does_not_duplicate_failure_records(tmp_path):
    from teleop.gello_cr.support.logging_config import configure_logging

    configure_logging(repo_root=tmp_path)
    configure_logging(repo_root=tmp_path)
    logging.getLogger("workbench.application").error("single failure record")
    assert read_log(tmp_path).count("single failure record") == 1


def test_failure_is_persisted_when_console_level_is_critical(tmp_path):
    from teleop.gello_cr.support.logging_config import configure_logging

    configure_logging("CRITICAL", repo_root=tmp_path)
    try:
        raise OSError("device failure while console is quiet")
    except OSError:
        logging.getLogger("workbench.application").exception("CONNECT failed")
    text = read_log(tmp_path)
    assert "device failure while console is quiet" in text
    assert "Traceback (most recent call last)" in text


def test_real_ui_config_error_is_logged_before_hardware_startup(tmp_path):
    config = tmp_path / "malformed.json"
    config.write_text("{")
    with pytest.raises((ValueError, RuntimeError)):
        entrypoint.main(["--repo-root", str(tmp_path), "--check-only", "--config", str(config)])
    text = read_log(tmp_path)
    assert "startup" in text.lower()
    assert "malformed.json" in text
    assert "Traceback (most recent call last)" in text


def test_workflow_preflight_exception_keeps_original_behavior_and_traceback(tmp_path, monkeypatch):
    from core.openpi.cr3_o6 import run_workflow as workflow

    monkeypatch.setattr(workflow, "REPO_ROOT", tmp_path)

    def broken_hardware_profile(path):
        raise ValueError("workflow hardware profile is invalid")

    monkeypatch.setattr(workflow, "load_hardware_config", broken_hardware_profile)
    with pytest.raises(ValueError, match="hardware profile is invalid"):
        workflow.run_workflow(tasks=[], config_path=None, policy_host="localhost", policy_port=8000)
    text = read_log(tmp_path)
    assert "workflow hardware profile is invalid" in text
    assert "Traceback (most recent call last)" in text


def test_async_command_error_callback_failure_is_persisted(tmp_path):
    from teleop.gello_cr.ui.command_port import AsyncApplicationCommandPort, CommandRequest

    initialize_logging(tmp_path)
    service = ApplicationService()
    callback_entered = threading.Event()

    def broken_connect(_payload):
        raise OSError("async controller connection refused")

    def broken_error_callback(request, error):
        callback_entered.set()
        raise RuntimeError("operator error display failed")

    service.set_handler(Command.CONNECT, broken_connect)
    port = AsyncApplicationCommandPort(service, error_callback=broken_error_callback)
    try:
        port.submit(CommandRequest.create(Command.CONNECT))
        assert callback_entered.wait(1.0)
    finally:
        port.close()

    text = read_log(tmp_path)
    assert "CONNECT" in text
    assert "async controller connection refused" in text
    assert "Command error callback failed" in text
    assert "operator error display failed" in text
    assert "Traceback (most recent call last)" in text


def test_workflow_helper_cleanup_failure_keeps_file_and_console_traceback(tmp_path, capsys):
    from core.openpi.cr3_o6.run_workflow import _close_hand

    initialize_logging(tmp_path)

    def broken_close():
        raise OSError("hand transport cleanup refused")

    _close_hand(SimpleNamespace(hand=SimpleNamespace(close=broken_close)))
    text = read_log(tmp_path)
    assert "Failed to close LinkerHand backend" in text
    assert "hand transport cleanup refused" in text
    assert "Traceback (most recent call last)" in text
    assert "hand transport cleanup refused" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["joint", "tcp_6d"])
def test_active_following_failure_keeps_original_traceback_and_ui_fault(
    tmp_path, following_loop, mode  # noqa: F811 - imported pytest fixture
):
    initialize_logging(tmp_path)
    events = queue.Queue()
    runtime = SimpleNamespace(events=events)
    following_loop.controller.hooks = replace(
        following_loop.controller.hooks,
        event=lambda level, message: TeleopRuntime._event(runtime, level, message),
    )

    def failed_servoj():
        raise OSError("ServoJ transport failed during following")

    following_loop.robot.on_send = failed_servoj
    following_loop.run(mode)
    assert following_loop.state.value == "fault"
    text = read_log(tmp_path)
    assert "ServoJ transport failed during following" in text
    assert "Traceback (most recent call last)" in text
    assert "failed_servoj" in text
    assert any(level == "error" for level, _ in list(events.queue))
