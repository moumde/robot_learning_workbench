"""Read-only application view model for Qt/PySide presentation.

The builder combines the workflow state, runtime snapshot and recorder snapshot
into one immutable object.  It performs no hardware I/O and dispatches no
commands.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core.workbench.core.state_machine import (
    Command,
    MotionState,
    RecordingState,
    RobotState,
    WorkflowState,
    WorkflowStateMachine,
)

from .permissions import RECORDING_SOURCES, OperationContext, operation_permission
from .service import ApplicationSnapshot

_WORKFLOW_LABELS = {
    WorkflowState.OFFLINE: "OFFLINE",
    WorkflowState.CONNECTED: "CONNECTED",
    WorkflowState.ROBOT_ENABLED: "ROBOT_ENABLED",
    WorkflowState.TELEOP_RUNNING: "TELEOP_RUNNING",
    WorkflowState.FAULT: "FAULT",
    WorkflowState.ESTOP: "ESTOP",
    WorkflowState.RETURNING_HOME: "RETURNING_HOME",
    WorkflowState.DAGGER_RUNNING: "DAGGER_RUNNING",
    WorkflowState.REPLAY_RUNNING: "REPLAY_RUNNING",
    WorkflowState.POINT_MOVE_RUNNING: "POINT_MOVE_RUNNING",
}


@dataclass(frozen=True, slots=True)
class ApplicationViewModel:
    workflow_state: WorkflowState
    recovery_state: WorkflowState
    workflow_label: str
    severity: str
    headline: str
    application_error: str
    runtime_state: str
    runtime_error: str
    recording_error: str
    dataset_session_active: bool
    episode_active: bool
    episode_pending: bool
    buffered_frames: int
    saved_episodes: int
    quality_needs_review: bool
    dagger_phase: str = ""
    dagger_root: str = ""
    dagger_expert_frames: int = 0
    motion_source: str = ""
    motion_mode: str = "IDLE"
    motion_running: bool = False
    dataset_format: str = "lerobot_v3"
    dataset_validation: Mapping[str, Any] | None = None
    robot_state: RobotState = RobotState.OFFLINE
    motion_state: MotionState = MotionState.IDLE
    recording_state: RecordingState = RecordingState.IDLE
    active_command: str = ""
    activity_text: str = ""
    actions: Mapping[Command, bool] = field(default_factory=dict)
    settings_editable: bool = False
    action_reasons: Mapping[Command, str] = field(default_factory=dict)
    recording_sources: Mapping[str, bool] = field(default_factory=dict)
    recording_source_reasons: Mapping[str, str] = field(default_factory=dict)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _runtime_error(snapshot: Mapping[str, Any]) -> str:
    return _text(snapshot.get("error") or snapshot.get("last_error") or "")


def _headline(
    state: WorkflowState,
    *,
    episode_active: bool,
    episode_pending: bool,
    buffered_frames: int,
) -> str:
    if state is WorkflowState.RETURNING_HOME:
        return "机械臂正在回 HOME · 可按紧急停止中断"
    if state is WorkflowState.POINT_MOVE_RUNNING:
        return "精确走点中 · 正在执行或等待目标到位"
    if state is WorkflowState.REPLAY_RUNNING:
        return "轨迹回放中 · 完成后保持停止"
    if state is WorkflowState.ESTOP:
        return "ESTOP：等待人工复位"
    if state is WorkflowState.FAULT:
        return "FAULT：等待排故 / 复位"
    if state is WorkflowState.TELEOP_RUNNING:
        return "TELEOP_RUNNING：主从跟随运行中"
    if state is WorkflowState.DAGGER_RUNNING:
        return "DAgger 运行中 · 空格切换专家接管 / 模型控制"
    if state is WorkflowState.ROBOT_ENABLED:
        return "ROBOT_ENABLED：机器人已使能，跟随未启动"
    if state is WorkflowState.CONNECTED:
        return "CONNECTED：控制器已连接，机器人未使能"
    return "OFFLINE：机器人未连接"


def build_application_view_model(
    application: ApplicationSnapshot,
    runtime: Mapping[str, Any],
    recorder: Mapping[str, Any],
    readiness: Mapping[str, Any] | None = None,
) -> ApplicationViewModel:
    state = application.state
    episode_active = bool(recorder.get("episode_active", False))
    buffered_frames = max(0, int(recorder.get("buffered_frames", 0) or 0))
    episode_pending = not episode_active and bool(
        recorder.get("episode_pending", buffered_frames > 0)
    )
    quality = recorder.get("quality") or {}
    if not isinstance(quality, Mapping):
        quality = {}

    application_error = _text(application.last_error)
    runtime_error = _runtime_error(runtime)
    recording_error = _text(recorder.get("error"))
    quality_needs_review = bool(quality.get("needs_review", False))

    if (
        state in (WorkflowState.FAULT, WorkflowState.ESTOP)
        or application_error
        or runtime_error
        or recording_error
    ):
        severity = "error"
    elif quality_needs_review or episode_pending:
        severity = "warning"
    else:
        severity = "info"

    machine = WorkflowStateMachine(
        state,
        recording_state=(
            RecordingState.RECORDING
            if episode_active
            else RecordingState.PENDING
            if episode_pending
            else RecordingState.IDLE
        ),
    )
    ready = readiness or {}
    context = OperationContext(state, machine.recording_state, recorder, runtime, readiness)
    permissions = {command: operation_permission(command, context) for command in Command}
    # FINISH needs an explicit outcome; expose each outcome through SAVE_* while
    # recording as well, so the controller can show accurate result choices.
    if episode_active:
        for command, outcome in (
            (Command.SAVE_SUCCESS, "success"),
            (Command.SAVE_FAILURE, "failure"),
        ):
            permissions[command] = operation_permission(
                Command.FINISH_EPISODE, context, {"outcome": outcome}
            )
    sources = {
        source: operation_permission(Command.START_EPISODE, context, {"source": source})
        for source in RECORDING_SOURCES
    }
    actions = {command: permission.allowed for command, permission in permissions.items()}
    actions[Command.FINISH_EPISODE] = any(
        permissions[command].allowed for command in (Command.SAVE_SUCCESS, Command.SAVE_FAILURE)
    )
    session_active = bool(recorder.get("session_active"))

    headline = _headline(
        state,
        episode_active=episode_active,
        episode_pending=episode_pending,
        buffered_frames=buffered_frames,
    )
    if episode_active:
        headline += f" · RECORDING：{buffered_frames} frames"
    elif episode_pending:
        headline += " · PENDING：等待成功 / 失败 / 丢弃"
    return ApplicationViewModel(
        actions=actions,
        action_reasons={command: permission.reason for command, permission in permissions.items()},
        recording_sources={source: permission.allowed for source, permission in sources.items()},
        recording_source_reasons={
            source: permission.reason for source, permission in sources.items()
        },
        settings_editable=state is WorkflowState.OFFLINE
        and not session_active
        and not (
            episode_active
            or episode_pending
            or ready.get("cameras_running")
            or ready.get("master_connected")
            or ready.get("o6_connected")
        ),
        robot_state=machine.robot_state,
        motion_state=(
            MotionState[str(runtime.get("motion", {}).get("source"))]
            if runtime.get("motion", {}).get("source") in MotionState.__members__
            else MotionState.IDLE
        ),
        recording_state=(
            RecordingState.SAVING
            if application.active_command
            in (Command.FINISH_EPISODE, Command.SAVE_SUCCESS, Command.SAVE_FAILURE)
            else RecordingState.FINALIZING
            if application.active_command in (Command.FINALIZE_DATASET, Command.FINALIZE_BATCH)
            else RecordingState.RECOVERING
            if application.active_command is Command.RESUME_BATCH
            else RecordingState.RECORDING
            if episode_active
            else RecordingState.PENDING
            if episode_pending
            else RecordingState.IDLE
        ),
        active_command=application.active_command.name if application.active_command else "",
        activity_text=command_activity(application.active_command),
        workflow_state=state,
        recovery_state=application.recovery_state,
        workflow_label=_WORKFLOW_LABELS[state],
        severity=severity,
        headline=headline,
        application_error=application_error,
        runtime_state=_text(runtime.get("state")) or "unknown",
        runtime_error=runtime_error,
        recording_error=recording_error,
        dataset_session_active=bool(recorder.get("session_active", False)),
        episode_active=episode_active,
        episode_pending=episode_pending,
        buffered_frames=buffered_frames,
        saved_episodes=max(
            0,
            int(recorder.get("saved_episodes", 0) or 0),
        ),
        quality_needs_review=quality_needs_review,
        dagger_phase=str(runtime.get("dagger", {}).get("phase", "")),
        dagger_root=str(runtime.get("dagger", {}).get("root", "")),
        dagger_expert_frames=int(runtime.get("dagger", {}).get("expert_frames", 0)),
        motion_source=str(runtime.get("motion", {}).get("source") or "IDLE"),
        motion_mode=str(runtime.get("motion", {}).get("mode", "IDLE")),
        motion_running=bool(runtime.get("motion", {}).get("running", False)),
        dataset_format=str(recorder.get("format") or "lerobot_v3"),
        dataset_validation=recorder.get("validation"),
    )


def command_activity(command):
    return {
        Command.CONNECT: "正在连接机器人",
        Command.PREPARE_DEVICES: "正在连接遥操设备",
        Command.START_CAMERAS: "正在启动相机",
        Command.START_TELEOP: "正在启动遥操",
        Command.START_EPISODE: "正在开始记录",
        Command.FINISH_EPISODE: "正在结束并保存 Episode",
        Command.SAVE_SUCCESS: "正在保存成功 Episode",
        Command.SAVE_FAILURE: "正在保存失败 Episode",
        Command.CREATE_DATASET: "正在创建数据集",
        Command.PLAN_MOTION: "正在规划",
        Command.REPLAY_TRAJECTORY: "正在启动回放",
        Command.FINALIZE_DATASET: "正在完成并合并数据集",
        Command.FINALIZE_BATCH: "正在合并批次",
        Command.VALIDATE_DATASET: "正在校验数据集",
        Command.RESUME_BATCH: "正在恢复批次",
        Command.LIST_DATASETS: "正在扫描数据集",
        Command.EXECUTE_PLAN: "正在启动规划轨迹",
    }.get(command, "正在处理" if command else "")
