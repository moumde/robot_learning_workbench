"""Top-level composition object for the new operator application."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teleop.gello_cr.hardware.camera_streams import resolve_camera_streams
from teleop.gello_cr.ui.backend import OperatorBackend

from .camera_service import CameraPollingService
from .dagger import DaggerBindings
from .preparation import (
    OperatorPreparationBindings,
    OperatorReadinessProvider,
)
from .runtime_factory import (
    ConcreteRuntime,
    ConcreteRuntimeFactory,
    RuntimeFactoryPaths,
)


@dataclass(slots=True)
class OperatorApplication:
    runtime: ConcreteRuntime
    backend: OperatorBackend
    cameras: CameraPollingService
    readiness: OperatorReadinessProvider
    preparation_bindings: OperatorPreparationBindings
    dagger: DaggerBindings | None = None

    _closed_resources: set[str] = field(default_factory=set, init=False)

    def close(self, timeout: float = 30.0, *, save_pending: bool = False) -> None:
        dataset = self.runtime.recorder.snapshot()
        if dataset.get("partial_episodes"):
            raise RuntimeError(
                "批次包含未处理 Partial：请先明确保留为 Failure、丢弃，或保留批次稍后继续"
            )
        if not save_pending and (
            dataset.get("episode_active")
            or dataset.get("episode_pending", bool(dataset.get("buffered_frames")))
        ):
            raise RuntimeError("Episode 未处理：请先停止录制并明确保存或丢弃，再退出")
        if (
            save_pending
            and not dataset.get("buffered_frames")
            and (dataset.get("episode_active") or dataset.get("episode_pending", False))
        ):
            raise RuntimeError("Episode 暂无可保存帧；请先结束录制并明确丢弃空 Episode，再退出")
        trajectory = self.runtime.teleop_engine.snapshot().get("trajectory", {})
        trajectory_unsaved = (
            trajectory.get("recording")
            or trajectory.get("pending")
            or trajectory.get("frame_count", 0)
        )
        if trajectory_unsaved and not save_pending:
            raise RuntimeError("轨迹未处理：请先停止并保存或取消记录，再退出")
        errors = []

        def attempt(name, operation):
            if name in self._closed_resources:
                return
            try:
                operation()
            except Exception as exc:
                exc.add_note(f"shutdown resource: {name}")
                errors.append(exc)
            else:
                self._closed_resources.add(name)

        # Reject queued commands before stopping producers. Never join completion
        # jobs while a normal handler still owns the dispatcher lock.
        self.backend.command_port.stop_accepting()
        attempt("sampling", self.runtime.recorder.stop_episode)
        attempt("motion", lambda: self.runtime.teleop_engine.shutdown(close_devices=False))
        attempt("commands", lambda: self.backend.command_port.close(timeout=timeout))
        attempt("completions", lambda: self.backend.bindings.close(timeout=timeout))
        if self.dagger is not None:
            attempt("dagger", self.dagger.close)
        # Live producers still own their feedback devices and pending writer.
        # Keep these resources available for a bounded, explicit shutdown retry.
        if errors:
            raise ExceptionGroup("Application shutdown incomplete", errors)
        if save_pending:
            if trajectory_unsaved:

                def save_trajectory():
                    self.runtime.teleop_engine.stop_trajectory_recording()
                    self.runtime.teleop_engine.save_trajectory()

                attempt("trajectory", save_trajectory)
            if self.runtime.recorder.snapshot().get("buffered_frames", 0):
                attempt(
                    "pending_episode",
                    lambda: self.runtime.recorder.save_episode(
                        "failure", "退出程序时保留未完成 Episode"
                    ),
                )
        attempt("cameras", self.cameras.close)
        attempt("runtime", self.runtime.close)
        attempt("recorder", self.runtime.recorder.close)
        if errors:
            raise ExceptionGroup("Application shutdown incomplete", errors)
        self.backend.presenter.close()


def build_operator_application(
    repo_root: str | Path,
    *,
    factory: Any | None = None,
    dagger_options: dict | None = None,
) -> OperatorApplication:
    paths = RuntimeFactoryPaths.from_repo(repo_root)
    runtime_factory = factory or ConcreteRuntimeFactory(paths)
    runtime = runtime_factory.build()

    dataset_cfg = runtime.store.data["dataset"]
    cameras = CameraPollingService(
        cameras=runtime.camera_devices,
        streams=resolve_camera_streams(dataset_cfg),
        sample_source=runtime.sample_source,
        poll_hz=float(dataset_cfg.get("camera_poll_hz", 30.0)),
    )
    readiness = OperatorReadinessProvider(
        runtime=runtime,
        cameras=cameras,
        robot_status_snapshot=runtime.cr3a_lifecycle.status_snapshot,
    )

    preview_snapshot = getattr(
        runtime.sample_source,
        "preview_snapshot",
        None,
    )
    if preview_snapshot is None:

        def preview_snapshot():
            return {}

    backend = OperatorBackend.compose(
        teleop_engine=runtime.teleop_engine,
        recorder=runtime.recorder,
        lifecycle=runtime.lifecycle,
        readiness_snapshot=readiness.snapshot,
        preview_snapshot=preview_snapshot,
        episode_metadata={"config": runtime.store.data},
    )

    preparation_bindings = OperatorPreparationBindings(
        backend.service,
        teleop_engine=runtime.teleop_engine,
        recorder=runtime.recorder,
        cameras=cameras,
    ).install()

    dagger = DaggerBindings(
        runtime,
        backend.service,
        readiness,
        **{
            "openpi_root": os.environ.get("GELLO_CR_OPENPI_ROOT", str(paths.repo_root)),
            **(dagger_options or {}),
        },
    ).install()

    return OperatorApplication(
        runtime=runtime,
        backend=backend,
        cameras=cameras,
        readiness=readiness,
        preparation_bindings=preparation_bindings,
        dagger=dagger,
    )
