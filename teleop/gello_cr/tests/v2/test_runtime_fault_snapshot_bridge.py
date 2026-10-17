
from __future__ import annotations

from gello_cr.app import ApplicationService
from gello_cr.core.state_machine import Command, WorkflowState
from gello_cr.ui.backend import RuntimeFaultSnapshotBridge


class Runtime:
    def __init__(self, state="idle", error="") -> None:
        self.state = state
        self.error = error

    def snapshot(self):
        return {
            "state": self.state,
            "last_error": self.error,
        }


def test_runtime_fault_snapshot_enters_application_fault() -> None:
    service = ApplicationService()
    runtime = Runtime("fault", "feedback timeout")
    bridge = RuntimeFaultSnapshotBridge(service, runtime)

    bridge.snapshot()

    assert service.state is WorkflowState.FAULT
    assert service.snapshot().last_error == "feedback timeout"


def test_estop_has_priority_over_runtime_fault_snapshot() -> None:
    service = ApplicationService()
    service.dispatch(Command.EMERGENCY_STOP)
    runtime = Runtime("fault", "late runtime fault")
    bridge = RuntimeFaultSnapshotBridge(service, runtime)

    bridge.snapshot()

    assert service.state is WorkflowState.ESTOP


def test_runtime_return_to_idle_does_not_auto_reset_application_fault() -> None:
    service = ApplicationService()
    runtime = Runtime("fault", "fault")
    bridge = RuntimeFaultSnapshotBridge(service, runtime)

    bridge.snapshot()
    assert service.state is WorkflowState.FAULT

    runtime.state = "idle"
    runtime.error = ""
    bridge.snapshot()

    assert service.state is WorkflowState.FAULT


def test_normal_runtime_snapshot_does_not_change_application_state() -> None:
    service = ApplicationService()
    runtime = Runtime("idle")
    bridge = RuntimeFaultSnapshotBridge(service, runtime)

    snapshot = bridge.snapshot()

    assert snapshot["state"] == "idle"
    assert service.state is WorkflowState.OFFLINE
