"""Shared operation policy for command execution and read-only presentation.

The context contains cached observations only. Hardware checks remain at the
runtime boundary immediately before a producer obtains its motion lease.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from teleop.gello_cr.core.state_machine import (
    Command,
    RecordingState,
    WorkflowState,
    WorkflowStateMachine,
)

RECORDING_SOURCES = {
    "teleop": WorkflowState.TELEOP_RUNNING,
    "replay": WorkflowState.REPLAY_RUNNING,
    "point_move": WorkflowState.POINT_MOVE_RUNNING,
}
SAFETY_COMMANDS = frozenset({Command.STOP_MOTION, Command.EMERGENCY_STOP, Command.REPORT_FAULT})
_MOTION_STARTS = frozenset(
    {
        Command.RETURN_HOME,
        Command.START_TELEOP,
        Command.START_TRAJECTORY_RECORDING,
        Command.REPLAY_TRAJECTORY,
        Command.EXECUTE_PLAN,
        Command.START_DAGGER,
    }
)


@dataclass(frozen=True, slots=True)
class OperationPermission:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class OperationContext:
    state: WorkflowState
    recording_state: RecordingState = RecordingState.IDLE
    recorder: Mapping[str, Any] | None = None
    runtime: Mapping[str, Any] | None = None
    readiness: Mapping[str, Any] | None = None

    @property
    def episode_state(self):
        if self.recorder is None:
            return self.recording_state
        if self.recorder.get("episode_active"):
            return RecordingState.RECORDING
        if self.recorder.get("episode_pending", bool(self.recorder.get("buffered_frames"))):
            return RecordingState.PENDING
        return RecordingState.IDLE


def operation_permission(command, context, payload=None):
    """Return one decision and a user-facing refusal reason for an operation."""
    data = payload or {}
    recording = context.episode_state
    episode_open = recording is not RecordingState.IDLE
    state = context.state
    recorder = context.recorder
    ready = context.readiness
    runtime = context.runtime or {}
    machine = WorkflowStateMachine(state, recording_state=recording)
    source = str(data.get("source", "teleop"))

    def deny(reason):
        return OperationPermission(False, reason)

    if command in (
        Command.START_COLLECTION,
        Command.FINISH_COLLECTION,
        Command.HOME_AND_SAVE_EPISODE,
    ):
        if not machine.can(command, source=source):
            if command is Command.START_COLLECTION:
                if episode_open:
                    return deny("请先保存或丢弃当前 Episode，再开始采集")
                if source != "teleop":
                    return deny("联动采集只用于遥操；其他来源请先启动对应运动")
                return operation_permission(Command.START_TELEOP, context, data)
            if command is Command.HOME_AND_SAVE_EPISODE:
                if recording is not RecordingState.RECORDING:
                    return deny("请先开始采集；待处理 Episode 请直接保存或丢弃")
                return operation_permission(Command.RETURN_HOME, context, data)
            return deny(
                "正在回 HOME，请等待到位"
                if state is WorkflowState.RETURNING_HOME
                else "当前没有待保存的 Episode"
            )
        if command is Command.START_COLLECTION:
            # The compound action explicitly starts follow before capture. All
            # ordinary capture readiness checks still apply to that target state.
            return operation_permission(
                Command.START_EPISODE, replace(context, state=WorkflowState.TELEOP_RUNNING), data
            )
        if command is Command.HOME_AND_SAVE_EPISODE:
            home = operation_permission(Command.RETURN_HOME, context, data)
            if not home.allowed:
                return home
            return operation_permission(Command.FINISH_EPISODE, context, {"outcome": "success"})
        return operation_permission(Command.FINISH_EPISODE, context, data)

    if command in SAFETY_COMMANDS:
        return OperationPermission(
            machine.can(command), "当前安全状态已生效" if not machine.can(command) else ""
        )
    if (
        command in (Command.REPLAY_TRAJECTORY, Command.EXECUTE_PLAN, Command.PLAN_MOTION)
        and recording is RecordingState.PENDING
    ):
        return deny("请先保存或丢弃待处理 Episode")
    if command in (Command.RESET_FAULT, Command.RESET_ESTOP) and episode_open:
        return deny("Episode 未处理；复位前请先保存失败或明确丢弃")
    if command is Command.START_EPISODE and RECORDING_SOURCES.get(source) is not state:
        return deny("请先启动所选采集来源：遥操、回放或精确走点")
    if command is Command.START_EPISODE and source != "teleop":
        if recorder is not None and not recorder.get("session_active"):
            return deny("回放或走点采集请先创建数据集，再启动运动和记录")
        motion = runtime.get("motion")
        if motion is not None and (
            not motion.get("running") or motion.get("source") != source.upper()
        ):
            return deny("所选采集运动已结束或被其他运动接管，请重新启动对应来源")
    if command is Command.FINISH_EPISODE:
        outcome = data.get("outcome")
        if outcome not in ("success", "failure"):
            return deny("请选择 Episode 结果 outcome：success 或 failure")
        if outcome == "success" and state in (WorkflowState.FAULT, WorkflowState.ESTOP):
            return deny("故障或紧急停止后只能保存失败 Episode 或丢弃")
    if not machine.can(command, source=source):
        if command is Command.RETURN_HOME:
            return deny("HOME 需要机器人明确使能，且无故障或紧急停止")
        if command is Command.START_TELEOP:
            if state is WorkflowState.OFFLINE:
                return deny("请先连接机器人，再明确上使能并准备遥操设备")
            if state is WorkflowState.CONNECTED:
                return deny("请先明确上使能机器人，再启用遥操")
            return deny("请先停止当前运动并处理故障，再启用遥操")
        return deny(f"{command.name} 当前不可用（{state.name} / {recording.name}）")

    if command in _MOTION_STARTS or command is Command.START_EPISODE:
        if runtime.get("state") in ("fault", "closed"):
            return deny("机器人故障或已关闭，请先排故复位")
        if runtime.get("servo_enabled") is False:
            return deny("请先明确上使能机器人")
        if ready is not None:
            if ready.get("robot_connected") is False:
                return deny("请先连接机器人")
            if ready.get("servo_state") is not None and ready["servo_state"] != "on":
                return deny("机器人 Servo 未确认 ON，请检查连接并明确上使能")
            capability = {
                Command.RETURN_HOME: "supports_home",
                Command.EXECUTE_PLAN: "supports_joint_control",
                Command.REPLAY_TRAJECTORY: "supports_joint_control",
            }.get(command)
            capabilities = ready.get("capabilities") or {}
            if capability in capabilities and not capabilities[capability]:
                return deny("当前机器人不支持此操作")
    if command is Command.RETURN_HOME:
        if runtime.get("state", "idle") not in (
            "idle",
            "following",
            "replay",
            "point_move",
            "dagger",
            "master_free",
        ) or runtime.get("o6_action_active"):
            return deny("HOME 或手部恢复动作正在执行，请先等待完成或停止")
    if command in (Command.PREPARE_DEVICES, Command.STOP_CAMERAS) and episode_open:
        return deny("Episode 未处理；请先保存或丢弃，再切换采集设备")
    if ready is not None:
        master_ready = ready.get("master_ready")
        if master_ready is None:
            master_ready = ready.get("master_connected")
        hand_ready = ready.get("hand_ready")
        if hand_ready is None:
            hand_ready = ready.get("o6_connected")
        devices_ready = bool(
            master_ready
            and not ready.get("master_error")
            and (not ready.get("hand_required", True) or hand_ready and not ready.get("o6_error"))
        )
        if command in (Command.START_EPISODE, Command.CREATE_DATASET):
            if not ready.get("camera_frames_ready") or ready.get("camera_error"):
                return deny(
                    "Camera frames are stale/unavailable: "
                    + str(ready.get("camera_error") or "请检查相机画面")
                )
        if command in (Command.START_TELEOP, Command.START_TRAJECTORY_RECORDING) or (
            command is Command.START_EPISODE and source == "teleop"
        ):
            if not devices_ready:
                return deny("遥操输入设备和手部尚未就绪，请检查连接与反馈")
        if command is Command.PREPARE_DEVICES and devices_ready:
            return deny("遥操设备已连接")
        if command is Command.START_CAMERAS and ready.get("cameras_running"):
            return deny("相机已启动")
        if command is Command.STOP_CAMERAS and not ready.get("cameras_running"):
            return deny("相机未启动")
    if (
        command in (Command.SAVE_SUCCESS, Command.SAVE_FAILURE, Command.FINISH_EPISODE)
        and recorder is not None
    ):
        if int(recorder.get("buffered_frames", 0) or 0) <= 0:
            return deny("暂无可保存帧；请明确丢弃本段 Episode")
        success = command is Command.SAVE_SUCCESS or (
            command is Command.FINISH_EPISODE and data.get("outcome") == "success"
        )
        if success and runtime.get("state") in ("fault", "closed"):
            return deny("机器人运行时已故障或关闭；只能保存失败 Episode 或丢弃")
        if success and recorder.get("error"):
            return deny("Episode 采集或写入出错；只能保存失败 Episode 或丢弃")
    if recorder is not None:
        session_active = bool(recorder.get("session_active"))
        if command is Command.CREATE_DATASET and (session_active or episode_open):
            return deny("当前数据集尚未结束，请先处理 Episode 并完成数据集")
        if command is Command.FINALIZE_DATASET and (not session_active or episode_open):
            return deny("请先处理当前 Episode，再完成已创建的数据集")
        if command is Command.SELECT_DATASET_FORMAT and session_active:
            return deny("数据集已创建，完成当前数据集后才能切换格式")
    return OperationPermission(True)
