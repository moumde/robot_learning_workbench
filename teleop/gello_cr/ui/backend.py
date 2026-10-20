"""Composition boundary between the application layer and runtime objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from teleop.gello_cr.app import (
    ApplicationService,
    RuntimeCommandBindings,
    RuntimeLifecycleCallbacks,
)
from teleop.gello_cr.core.state_machine import WorkflowState

from .command_port import AsyncApplicationCommandPort
from .presenter import OperatorUiPresenter

SnapshotSource = Callable[[], Mapping[str, Any]]


class SnapshotRuntime(Protocol):
    def snapshot(self) -> Mapping[str, Any]: ...


class SnapshotRecorder(Protocol):
    def snapshot(self) -> Mapping[str, Any]: ...


class RuntimeFaultSnapshotBridge:
    """Read runtime snapshot and synchronize an already-handled fault."""

    def __init__(
        self,
        service: ApplicationService,
        runtime: SnapshotRuntime,
    ) -> None:
        self._service = service
        self._runtime = runtime

    def snapshot(self) -> Mapping[str, Any]:
        snapshot = dict(self._runtime.snapshot())
        runtime_state = str(snapshot.get("state", "")).strip().lower()

        if runtime_state == "fault" and self._service.state is not WorkflowState.ESTOP:
            reason = str(
                snapshot.get("last_error") or snapshot.get("error") or "runtime fault"
            ).strip()
            self._service.report_external_fault(
                reason,
                {
                    "runtime": "teleop",
                    "runtime_state": runtime_state,
                },
            )

        return snapshot


@dataclass(slots=True)
class OperatorBackend:
    service: ApplicationService
    bindings: RuntimeCommandBindings
    command_port: AsyncApplicationCommandPort
    presenter: OperatorUiPresenter
    runtime_fault_bridge: RuntimeFaultSnapshotBridge
    teleop_engine: Any
    recorder: Any

    @classmethod
    def compose(
        cls,
        *,
        teleop_engine: Any,
        recorder: Any,
        lifecycle: RuntimeLifecycleCallbacks,
        readiness_snapshot: SnapshotSource | None = None,
        preview_snapshot: SnapshotSource | None = None,
        episode_metadata: Mapping[str, Any] | None = None,
        event_capacity: int = 256,
        normal_command_capacity: int = 32,
        safety_command_capacity: int = 8,
    ) -> OperatorBackend:
        if not hasattr(teleop_engine, "snapshot"):
            raise TypeError("teleop_engine must provide snapshot()")
        if not hasattr(recorder, "snapshot"):
            raise TypeError("recorder must provide snapshot()")

        service = ApplicationService()
        bindings = RuntimeCommandBindings(
            service,
            teleop_engine=teleop_engine,
            recorder=recorder,
            lifecycle=lifecycle,
            recording_snapshot=recorder.snapshot,
            episode_metadata=episode_metadata,
            readiness_snapshot=readiness_snapshot,
        ).install()

        runtime_fault_bridge = RuntimeFaultSnapshotBridge(
            service,
            teleop_engine,
        )
        presenter = OperatorUiPresenter(
            service,
            runtime_snapshot=runtime_fault_bridge.snapshot,
            recorder_snapshot=recorder.snapshot,
            catalog_snapshot=bindings.datasets.snapshot,
            readiness_snapshot=readiness_snapshot,
            preview_snapshot=preview_snapshot,
            event_capacity=event_capacity,
        )
        command_port = AsyncApplicationCommandPort(
            service,
            normal_capacity=normal_command_capacity,
            safety_capacity=safety_command_capacity,
        )

        return cls(
            service=service,
            bindings=bindings,
            command_port=command_port,
            presenter=presenter,
            runtime_fault_bridge=runtime_fault_bridge,
            teleop_engine=teleop_engine,
            recorder=recorder,
        )

    def close(self, timeout: float = 1.0) -> None:
        self.command_port.close(timeout=timeout)
        self.bindings.close(timeout)
        self.presenter.close()
