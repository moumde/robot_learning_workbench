"""The operator distinguishes a connected device from usable feedback."""

import time
from types import SimpleNamespace

from teleop.gello_cr.app import ApplicationService, build_application_view_model
from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.bootstrap.operator_app import build_operator_application
from teleop.gello_cr.bootstrap.preparation import OperatorReadinessProvider
from teleop.gello_cr.core.state_machine import Command, WorkflowState, WorkflowStateMachine
from teleop.gello_cr.ui.readiness import OperatorReadiness


def test_production_readiness_uses_cached_robot_feedback_for_permissions(tmp_path):
    store = TeleopConfigStore(tmp_path / "config" / "workbench.json")
    store.data["dataset"]["root"] = str(tmp_path / "datasets")
    store.data["dataset"]["staging_root"] = str(tmp_path / "staging")
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    store.save()
    operator = build_operator_application(tmp_path)
    try:
        service = ApplicationService(
            state_machine=WorkflowStateMachine(WorkflowState.ROBOT_ENABLED)
        )
        service.set_permission_sources(readiness_snapshot=operator.readiness.snapshot)
        lifecycle = operator.runtime.cr3a_lifecycle
        for connected, servo, age, error, expected_servo, allowed in (
            (True, "on", 0, "", "on", True),
            (True, "on", 2, "", "unknown", False),
            (True, "error", 0, "Servo 反馈读取失败", "error", False),
            (False, "off", 0, "机器人连接已断开", "off", False),
        ):
            with lifecycle._status_lock:
                lifecycle._status.update(
                    connected=connected,
                    servo_state=servo,
                    sampled_at=time.monotonic() - age,
                    error=error,
                )
            snapshot = operator.readiness.snapshot()
            assert snapshot["robot_connected"] is connected
            readiness = OperatorReadiness.from_mapping(snapshot)
            assert readiness.servo_state == expected_servo
            if age == 0:
                assert readiness.robot_error == error
            else:
                assert "过期" in readiness.robot_error
            view = build_application_view_model(service.snapshot(), {}, {}, snapshot)
            assert view.actions[Command.RETURN_HOME] is allowed
            assert service.can(Command.RETURN_HOME) is allowed
    finally:
        operator.close()


def test_connected_master_with_stale_feedback_is_not_teleop_ready():
    now = time.monotonic()
    master = SimpleNamespace(
        master_type="gello",
        connected=True,
        error="",
        latest=lambda: SimpleNamespace(timestamp=now - 2),
    )
    hand = SimpleNamespace(connected=True, error="", latest=lambda: ([0] * 6, [0] * 6, now))
    runtime = SimpleNamespace(
        master_controller=master,
        o6_controller=hand,
        sample_source=SimpleNamespace(readiness_error=lambda: ""),
        cr3a_lifecycle=SimpleNamespace(
            status_snapshot=lambda: {
                "connected": True,
                "servo_state": "on",
                "error": "",
                "sampled_at": now,
            }
        ),
        store=SimpleNamespace(
            data={
                "hardware": {"profile": "cr3a_o6", "name": "现场机械臂"},
                "robot": {"ip": "192.0.2.10", "robot_num": 1},
                "master": {"type": "gello"},
                "gello": {"feedback_timeout_s": 0.5, "port": "/nonexistent/gello"},
                "o6": {"feedback_timeout_s": 1.2},
            }
        ),
    )
    cameras = SimpleNamespace(snapshot=lambda: SimpleNamespace(running=False, error=""))
    snapshot = OperatorReadinessProvider(
        runtime=runtime,
        cameras=cameras,
        robot_status_snapshot=runtime.cr3a_lifecycle.status_snapshot,
    ).snapshot()
    readiness = OperatorReadiness.from_mapping(snapshot)

    assert readiness.master_connected
    assert not readiness.devices_ready
    assert "过期" in readiness.master_error
    assert readiness.robot_name == "现场机械臂"
    assert readiness.servo_state == "on"
    assert readiness.capabilities.supports_home


def test_optional_end_effector_does_not_block_a_generic_robot():
    readiness = OperatorReadiness.from_mapping(
        {
            "master_connected": True,
            "master_ready": True,
            "o6_connected": False,
            "hand_required": False,
            "capabilities": {"supports_home": False, "supports_gripper": False},
        }
    )

    assert readiness.devices_ready
    assert not readiness.capabilities.supports_home


def test_explicit_unknown_servo_is_preserved_in_operator_status():
    readiness = OperatorReadiness.from_mapping(
        {
            "robot_connected": True,
            "servo_state": "unknown",
            "robot_error": "反馈读取失败",
        }
    )

    assert readiness.robot_connected
    assert readiness.servo_state == "unknown"
    assert readiness.robot_error == "反馈读取失败"
