"""Framework-independent presenter for the operator UI."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from gello_cr.app import (
    AppEvent,
    ApplicationEventBuffer,
    ApplicationService,
    ApplicationViewModel,
    build_application_view_model,
)

from .preview_model import CameraPreview
from .readiness import OperatorReadiness

SnapshotSource = Callable[[], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class UiFrame:
    view_model: ApplicationViewModel
    events: tuple[AppEvent, ...]
    readiness: OperatorReadiness = OperatorReadiness()
    preview: CameraPreview = CameraPreview()
    trajectory: Mapping[str, Any] = field(default_factory=dict)
    planning: Mapping[str, Any] = field(default_factory=dict)
    catalog: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    dataset: Mapping[str, Any] = field(default_factory=dict)


class OperatorUiPresenter:
    """Read-only presentation adapter used by Qt/PySide UI layers."""

    def __init__(
        self,
        service: ApplicationService,
        *,
        runtime_snapshot: SnapshotSource,
        recorder_snapshot: SnapshotSource,
        catalog_snapshot: SnapshotSource | None = None,
        readiness_snapshot: SnapshotSource | None = None,
        preview_snapshot: SnapshotSource | None = None,
        event_capacity: int = 256,
    ) -> None:
        self._service = service
        self._runtime_snapshot = runtime_snapshot
        self._recorder_snapshot = recorder_snapshot
        self._catalog_snapshot = catalog_snapshot
        self._readiness_snapshot = readiness_snapshot
        self._preview_snapshot = preview_snapshot
        self._events = ApplicationEventBuffer(capacity=event_capacity)
        self._unsubscribe = service.subscribe(self._events.push)
        self._closed = False
        self.dataset_root = ""

    @property
    def closed(self) -> bool:
        return self._closed

    def poll(self) -> UiFrame:
        if self._closed:
            raise RuntimeError("operator UI presenter is closed")

        runtime = dict(self._runtime_snapshot())
        recorder = dict(self._recorder_snapshot())
        self.dataset_root = str(recorder.get("root", ""))

        readiness_source = self._readiness_snapshot
        readiness = OperatorReadiness.from_mapping(
            readiness_source() if readiness_source is not None else None
        )

        preview_source = self._preview_snapshot
        preview = CameraPreview.from_mapping(
            preview_source() if preview_source is not None else None
        )

        view_model = build_application_view_model(
            self._service.snapshot(),
            runtime,
            recorder,
            asdict(readiness),
        )
        return UiFrame(
            view_model=view_model,
            events=self._events.drain(),
            readiness=readiness,
            preview=preview,
            trajectory=runtime.get("trajectory", {}),
            planning=runtime.get("planning", {}),
            dataset=recorder,
            catalog=self._catalog_snapshot() if self._catalog_snapshot else {},
            diagnostics=runtime.get("diagnostics", {}),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._unsubscribe()
