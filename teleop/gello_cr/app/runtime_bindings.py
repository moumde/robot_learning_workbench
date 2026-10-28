"""Bind ApplicationService commands to motion orchestration and recording.

Robot connection and power callbacks are supplied by the bootstrap lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from teleop.gello_cr.core.state_machine import Command, InvalidTransition, WorkflowState
from teleop.gello_cr.trajectory import ReplayMode, ReplayOptions

from .background import BackgroundJobs
from .datasets import DatasetCatalog
from .permissions import OperationContext, operation_permission
from .service import ApplicationService, CommandSuperseded

LifecycleCallback = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class RuntimeLifecycleCallbacks:
    """Lifecycle operations still owned outside TeleopEngine.

    Missing callbacks are intentionally not treated as no-ops.  A command whose
    callback is absent fails before the WorkflowStateMachine advances.
    """

    connect: LifecycleCallback | None = None
    disconnect: LifecycleCallback | None = None
    power_on: LifecycleCallback | None = None
    power_off: LifecycleCallback | None = None
    reset_fault: LifecycleCallback | None = None
    reset_estop: LifecycleCallback | None = None


class RuntimeCommandBindings:
    """Register current runtime operations as ApplicationService handlers."""

    def __init__(
        self,
        service: ApplicationService,
        *,
        teleop_engine: Any,
        recorder: Any,
        lifecycle: RuntimeLifecycleCallbacks | None = None,
        readiness_snapshot: Callable[[], Mapping[str, Any]] | None = None,
        recording_snapshot: Callable[[], Mapping[str, Any]] | None = None,
        episode_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.recording_snapshot = recording_snapshot or getattr(recorder, "snapshot", None)
        self.episode_metadata = dict(episode_metadata or {})
        self.readiness_snapshot = readiness_snapshot
        self.service = service
        self.teleop_engine = teleop_engine
        self.recorder = recorder
        self.datasets = DatasetCatalog(recorder)
        self.lifecycle = lifecycle or RuntimeLifecycleCallbacks()
        self._trajectory_run = None
        self._trajectory_serial = 0
        self._trajectory_recording_run = None
        self._trajectory_recording_serial = 0
        self._point_serial = 0
        self._point_run = None
        self._completion_jobs = BackgroundJobs()

    def install(self) -> RuntimeCommandBindings:
        self.service.set_recording_snapshot(self.recording_snapshot)
        self.service.set_permission_sources(
            runtime_snapshot=getattr(self.teleop_engine, "operation_snapshot", None)
            or getattr(self.teleop_engine, "snapshot", None),
            readiness_snapshot=self.readiness_snapshot,
        )
        set_recording_snapshot = getattr(self.teleop_engine, "set_recording_snapshot", None)
        if callable(set_recording_snapshot):
            set_recording_snapshot(self.recording_snapshot)
        handlers = {
            Command.STOP_MOTION: self._stop_motion,
            Command.REFRESH_ROBOT_STATUS: lambda p: self.teleop_engine.refresh_robot_status(),
            Command.LIST_DATASETS: lambda p: self.datasets.scan(self._required_text(p, "root")),
            Command.VALIDATE_DATASET: lambda p: self.datasets.validate(
                self._required_text(p, "path")
            ),
            Command.READ_MOTION_POSITION: lambda p: self.teleop_engine.point_motion.read_position(),
            Command.PLAN_MOTION: lambda p: self.teleop_engine.point_motion.plan(dict(p)),
            Command.SAVE_MOTION_PLAN: lambda p: self.teleop_engine.point_motion.save(
                self._required_text(p, "plan_id")
            ),
            Command.EXECUTE_PLAN: self._execute_plan,
            Command.STOP_POINT_MOTION: self._stop_point_motion,
            Command.POINT_MOTION_COMPLETED: self._point_completed,
            Command.START_TRAJECTORY_RECORDING: self._start_trajectory_recording,
            Command.STOP_TRAJECTORY_RECORDING: self._stop_trajectory_recording,
            Command.SAVE_TRAJECTORY: lambda p: self.teleop_engine.save_trajectory(),
            Command.CANCEL_TRAJECTORY_RECORDING: self._cancel_trajectory_recording,
            Command.LIST_TRAJECTORIES: lambda p: self.teleop_engine.list_trajectories(),
            Command.PREVIEW_TRAJECTORY: lambda p: self.teleop_engine.preview_trajectory(
                self._required_text(p, "trajectory_id")
            ),
            Command.IMPORT_TRAJECTORY: lambda p: self.teleop_engine.import_trajectory(
                self._required_text(p, "path"),
                p.get("source", "legacy_json"),
                p.get("episode_index", 0),
            ),
            Command.REPLAY_TRAJECTORY: self._replay_trajectory,
            Command.STOP_TRAJECTORY_REPLAY: self._stop_trajectory_replay,
            Command.TRAJECTORY_COMPLETED: self._trajectory_completed,
            Command.CONNECT: self._connect,
            Command.DISCONNECT: self._disconnect,
            Command.POWER_ON: self._power_on,
            Command.POWER_OFF: self._power_off,
            Command.START_TELEOP: self._start_teleop,
            Command.STOP_TELEOP: self._stop_teleop,
            Command.START_EPISODE: self._start_episode,
            Command.SELECT_DATASET_FORMAT: self._select_dataset_format,
            Command.CREATE_DATASET: self._create_dataset,
            Command.SCAN_RECOVERABLE_BATCHES: lambda p: self.recorder.refresh_recovery(),
            Command.RESUME_BATCH: lambda p: self.recorder.recovery.resume(
                self._required_text(p, "batch_id")
            ),
            Command.FINALIZE_BATCH: lambda p: self.recorder.recovery.finalize(
                self._required_text(p, "batch_id")
            ),
            Command.DISCARD_BATCH: lambda p: self.recorder.recovery.discard(
                self._required_text(p, "batch_id")
            ),
            Command.RESOLVE_PARTIAL_EPISODE: lambda p: self.recorder.recovery.resolve_partial(
                self._required_text(p, "batch_id"),
                int(p["episode_index"]),
                self._required_text(p, "decision"),
            ),
            Command.SUSPEND_BATCH: lambda p: self.recorder.suspend("operator suspension"),
            Command.STOP_EPISODE: self._stop_episode,
            Command.FINISH_EPISODE: self._finish_episode,
            Command.FINALIZE_DATASET: lambda p: self.recorder.finalize(),
            Command.SAVE_SUCCESS: self._save_success,
            Command.SAVE_FAILURE: self._save_failure,
            Command.DISCARD_EPISODE: self._discard_episode,
            Command.REPORT_FAULT: self._report_fault,
            Command.RESET_FAULT: self._reset_fault,
            Command.EMERGENCY_STOP: self._emergency_stop,
            Command.RESET_ESTOP: self._reset_estop,
            Command.HOME_COMPLETED: self._home_completed,
            Command.RETURN_HOME: self._return_home,
        }
        for command, handler in handlers.items():
            self.service.set_handler(command, handler)
        return self

    @staticmethod
    def _require_callback(
        callback: LifecycleCallback | None,
        command: Command,
    ) -> LifecycleCallback:
        if callback is None:
            raise RuntimeError(f"{command.name} runtime lifecycle callback is not configured")
        return callback

    @staticmethod
    def _required_text(
        payload: Mapping[str, Any],
        key: str,
    ) -> str:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise ValueError(f"{key} is required")
        return value

    def _connect(self, _payload: Mapping[str, Any]) -> Any:
        return self._require_callback(
            self.lifecycle.connect,
            Command.CONNECT,
        )()

    def _disconnect(self, _payload: Mapping[str, Any]) -> Any:
        return self._require_callback(
            self.lifecycle.disconnect,
            Command.DISCONNECT,
        )()

    def _require_readiness(self, *, cameras: bool = False) -> None:
        if self.readiness_snapshot is None:
            return  # Legacy binding keeps its existing runtime validation.
        ready = self.readiness_snapshot()
        if cameras:
            if ready["camera_error"] or not ready["camera_frames_ready"]:
                raise RuntimeError("Camera frames are stale/unavailable: " + ready["camera_error"])
        elif not (ready["master_connected"] and ready["o6_connected"]):
            raise RuntimeError("GELLO/master and O6 must be ready before this command")

    def _power_on(self, _payload: Mapping[str, Any]) -> Any:
        # Enabling the connected arm also supports replay without a master or
        # hand. Follow and replay validate their own required input channels.
        return self._require_callback(
            self.lifecycle.power_on,
            Command.POWER_ON,
        )()

    def _power_off(self, _payload: Mapping[str, Any]) -> Any:
        return self._require_callback(
            self.lifecycle.power_off,
            Command.POWER_OFF,
        )()

    def _start_teleop(self, _payload: Mapping[str, Any]) -> Any:
        self._require_permission(Command.START_TELEOP, _payload)
        return self.teleop_engine.start_follow()

    def _stop_teleop(self, payload: Mapping[str, Any]) -> Any:
        reason = str(payload.get("reason", "application command")).strip() or "application command"
        if payload.get("follow_started_at") is not None:
            stopped = self.teleop_engine.stop_follow(
                reason, expected_started_at=payload["follow_started_at"]
            )
            if stopped is False:
                raise CommandSuperseded("原采集遥操已被 HOME 或其他运动接管")
            return stopped
        return self.teleop_engine.stop_follow(reason)

    def _start_episode(self, payload: Mapping[str, Any]) -> Any:
        self._require_readiness(cameras=True)
        task = self._required_text(payload, "task")
        base_root = self._required_text(payload, "base_root")
        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        self._require_permission(Command.START_EPISODE, payload)
        if (
            callable(getattr(self.recorder, "prepare_dataset", None))
            and not self.recorder.snapshot().get("session_active")
        ):
            self._create_dataset(payload)
        wait_ready = getattr(self.teleop_engine, "wait_follow_ready", None)
        if payload.get("source", "teleop") == "teleop" and callable(wait_ready):
            wait_ready()
        self._require_permission(Command.START_EPISODE, payload)
        return self.recorder.start_episode(
            task,
            base_root,
            metadata={
                **self.episode_metadata,
                **dict(metadata or {}),
                "recording_source": str(payload.get("source", "teleop")),
                **(
                    {"task_description": str(payload["description"])}
                    if payload.get("description")
                    else {}
                ),
            },
        )

    def _select_dataset_format(self, payload):
        if self.recorder.snapshot().get("session_active"):
            raise RuntimeError("数据集已创建，完成当前数据集后才能切换格式")
        self.recorder.writer_factory.select(self._required_text(payload, "format"))

    def _create_dataset(self, payload):
        self._require_readiness(cameras=True)
        prepare = getattr(self.recorder, "prepare_dataset", None)
        if callable(prepare):
            return prepare(
                self._required_text(payload, "task"),
                self._required_text(payload, "base_root"),
                task_description=str(payload.get("description", "")),
                allow_environment_setup=self.service.state in (
                    WorkflowState.OFFLINE, WorkflowState.CONNECTED, WorkflowState.ROBOT_ENABLED,
                ),
            )
        return self.recorder.create_dataset(
            self._required_text(payload, "task"),
            self._required_text(payload, "base_root"),
            **(
                {"task_description": str(payload["description"])}
                if "description" in payload
                else {}
            ),
        )

    def _stop_episode(self, _payload: Mapping[str, Any]) -> Any:
        return self.recorder.stop_episode()

    def _finish_episode(self, payload: Mapping[str, Any]) -> Any:
        outcome = payload.get("outcome")
        if outcome not in ("success", "failure"):
            raise ValueError("请选择 Episode 结果 outcome：success 或 failure")
        self.recorder.stop_episode()
        return (self._save_success if outcome == "success" else self._save_failure)(payload)

    def _require_permission(self, command, payload=None):
        application = self.service.snapshot()
        runtime_snapshot = getattr(self.teleop_engine, "operation_snapshot", None) or getattr(
            self.teleop_engine,
            "snapshot",
            None,
        )
        # Recheck the binding's live providers immediately before side effects,
        # including callers that invoke a concrete operation before install().
        permission = operation_permission(
            command,
            OperationContext(
                application.state,
                application.recording_state,
                self.recording_snapshot() if self.recording_snapshot else None,
                runtime_snapshot() if runtime_snapshot else None,
                self.readiness_snapshot() if self.readiness_snapshot else None,
            ),
            payload,
        )
        if not permission.allowed:
            raise InvalidTransition(permission.reason)

    def _save_success(self, payload: Mapping[str, Any]) -> Any:
        self._require_permission(Command.SAVE_SUCCESS, payload)
        return self.recorder.save_episode(
            "success",
            str(payload.get("notes", "")),
        )

    def _save_failure(self, payload: Mapping[str, Any]) -> Any:
        self._require_permission(Command.SAVE_FAILURE, payload)
        return self.recorder.save_episode(
            "failure",
            str(payload.get("notes", "")),
        )

    def _discard_episode(self, _payload: Mapping[str, Any]) -> Any:
        return self.recorder.discard_episode()

    def _report_fault(self, payload: Mapping[str, Any]) -> Any:
        reason = str(payload.get("reason", "runtime fault")).strip() or "runtime fault"
        return self.teleop_engine.emergency_stop(f"故障停止：{reason}")

    def _emergency_stop(self, payload: Mapping[str, Any]) -> Any:
        reason = str(payload.get("reason", "软件紧急停止")).strip() or "软件紧急停止"
        return self.teleop_engine.emergency_stop(reason)

    def _require_episode_resolved(self) -> None:
        if self.recording_snapshot is not None:
            episode = self.recording_snapshot()
            if episode.get("episode_active") or episode.get(
                "episode_pending", bool(episode.get("buffered_frames"))
            ):
                raise RuntimeError("Episode 未处理；复位前请先保存失败或明确丢弃")

    def _home_completed(self, _payload: Mapping[str, Any]) -> None:
        if self.teleop_engine.state != "idle":
            raise RuntimeError("HOME 完成状态已被其他动作或停止覆盖")

    def _return_home(self, _payload: Mapping[str, Any]) -> None:
        self._trajectory_run = self._point_run = self._trajectory_recording_run = None
        self.teleop_engine.return_home()
        self._home_completed(_payload)

    def _reset_fault(self, _payload: Mapping[str, Any]) -> Any:
        self._require_episode_resolved()
        return self._require_callback(
            self.lifecycle.reset_fault,
            Command.RESET_FAULT,
        )()

    def _reset_estop(self, _payload: Mapping[str, Any]) -> Any:
        self._require_episode_resolved()
        return self._require_callback(
            self.lifecycle.reset_estop,
            Command.RESET_ESTOP,
        )()

    def _start_trajectory_recording(self, payload):
        self._require_permission(Command.START_TRAJECTORY_RECORDING, payload)
        name = self._required_text(payload, "name")
        self._trajectory_recording_serial += 1
        run = self._trajectory_recording_run = self._trajectory_recording_serial
        try:
            return self.teleop_engine.start_trajectory_recording(
                name, on_finished=lambda error: self._trajectory_recording_finished(run, error)
            )
        except Exception:
            if self._trajectory_recording_run == run:
                self._trajectory_recording_run = None
            self._report_trajectory_cleanup_fault()
            raise

    def _report_trajectory_cleanup_fault(self):
        if self.teleop_engine.state == "fault":
            self.service.report_external_fault(self.teleop_engine.last_error)

    def _trajectory_recording_finished(self, run, error):
        if run != self._trajectory_recording_run:
            return
        if error or self.teleop_engine.state == "fault":
            self._trajectory_recording_run = None
            self.service.report_external_fault(
                "轨迹录制停止：" + str(error or self.teleop_engine.last_error)
            )
            return
        self._completion_jobs.start(
            lambda: self._finish_recording_run(run), name="Trajectory-Recording-Completion"
        )

    def _finish_recording_run(self, run):
        try:
            self.service.dispatch(Command.STOP_TRAJECTORY_RECORDING, {"recording_run": run})
        except (InvalidTransition, OSError):
            # A newer operation owns motion, or a failed save remains retryable.
            pass

    def _stop_trajectory_recording(self, payload):
        if (
            "recording_run" in payload
            and payload["recording_run"] != self._trajectory_recording_run
        ):
            raise InvalidTransition("Trajectory recording completion belongs to an earlier run")
        self._trajectory_recording_run = None
        try:
            self.teleop_engine.stop_trajectory_recording()
        except Exception:
            self._report_trajectory_cleanup_fault()
            raise
        try:
            return self.teleop_engine.save_trajectory()
        except Exception as exc:
            # Physical stop has succeeded; storage failure must not retain a
            # TELEOP_RUNNING workflow while Retry Save owns pending frames.
            exc.trajectory_recording_stopped = True
            raise

    def _cancel_trajectory_recording(self, _payload):
        self._trajectory_recording_run = None
        try:
            return self.teleop_engine.cancel_trajectory_recording()
        except Exception:
            self._report_trajectory_cleanup_fault()
            raise

    def _replay_trajectory(self, payload):
        self._require_permission(Command.REPLAY_TRAJECTORY, payload)
        options = dict(payload.get("options", {}))
        options["mode"] = ReplayMode(options.get("mode", "relative"))
        if options.get("joint_mask") is not None:
            options["joint_mask"] = tuple(options["joint_mask"])
        self._trajectory_serial += 1
        run = self._trajectory_run = self._trajectory_serial
        return self.teleop_engine.replay_trajectory(
            self._required_text(payload, "trajectory_id"),
            ReplayOptions(**options),
            on_finished=lambda error: self._trajectory_finished(run, error),
        )

    def _stop_trajectory_replay(self, _payload):
        self._trajectory_run = None
        return self.teleop_engine.stop_trajectory_replay()

    def _trajectory_completed(self, payload):
        # Checked under normal dispatch serialization: an old completion must
        # never finish a newer replay that started while this notice waited.
        if self._trajectory_run is None or payload.get("run") != self._trajectory_run:
            raise InvalidTransition("Trajectory completion belongs to an earlier replay")
        self._trajectory_run = None

    def _trajectory_finished(self, run, error):
        if error:
            if run == self._trajectory_run:
                self.service.report_external_fault(f"轨迹回放失败：{error}")
            return
        # STOP holds the command lock while joining the playback worker. Its
        # completion must return immediately and dispatch from another thread.
        self._completion_jobs.start(
            lambda: self._dispatch_trajectory_completion(run), name="Trajectory-Completion"
        )

    def _dispatch_trajectory_completion(self, run):
        try:
            self.service.dispatch(Command.TRAJECTORY_COMPLETED, {"run": run})
        except InvalidTransition:
            pass  # STOP/HOME/ESTOP or a newer replay already owns the workflow.

    def _execute_plan(self, payload):
        self._require_permission(Command.EXECUTE_PLAN, payload)
        self._point_serial += 1
        run = self._point_run = self._point_serial
        try:
            return self.teleop_engine.point_motion.execute(
                self._required_text(payload, "plan_id"),
                on_finished=lambda error: self._point_finished(run, error),
            )
        except Exception:
            self._point_run = None
            raise

    def _stop_point_motion(self, payload):
        self._point_run = None
        return self.teleop_engine.point_motion.stop()

    def _point_completed(self, payload):
        if self._point_run is None or payload.get("run") != self._point_run:
            raise InvalidTransition("Point motion completion belongs to an earlier execution")
        self._point_run = None

    def _point_finished(self, run, error):
        if error:
            if run == self._point_run:
                self.service.report_external_fault(f"精确走点失败：{error}")
            return
        self._completion_jobs.start(
            lambda: self._dispatch_point_completion(run), name="Point-Motion-Completion"
        )

    def _dispatch_point_completion(self, run):
        try:
            self.service.dispatch(Command.POINT_MOTION_COMPLETED, {"run": run})
        except InvalidTransition:
            pass

    def _stop_motion(self, payload):
        self._trajectory_run = self._point_run = None
        try:
            return self.teleop_engine.stop_motion(str(payload.get("reason", "人工停止运动")))
        finally:
            if self.recording_snapshot is not None and self.recording_snapshot().get(
                "episode_active"
            ):
                self.recorder.stop_episode()

    def close(self, timeout=3.0):
        self._trajectory_run = self._point_run = self._trajectory_recording_run = None
        self._completion_jobs.close(timeout)
