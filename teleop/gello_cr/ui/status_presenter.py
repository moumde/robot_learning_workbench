"""Persistent operator status, derived from one frame and cached feedback."""

from teleop.gello_cr.app.view_model import command_activity

from .controllers.collection_controller import episode_label
from .theme import set_state


def render_status(window, frame, pending=(), local_error=""):
    view, ready, dataset = frame.view_model, frame.readiness, frame.dataset
    errors = []
    seen = set()
    for source, message in (
        ("机器人", ready.robot_error),
        ("运动", view.runtime_error),
        ("操作", view.application_error),
        ("Recorder", view.recording_error),
        ("相机", ready.camera_error),
        ("输入设备", ready.master_error),
        ("末端", ready.o6_error),
        ("界面", local_error),
    ):
        if message and message not in seen:
            errors.append(f"{source}：{message}")
            seen.add(message)
    safety = view.robot_state.name in ("FAULT", "ESTOP")
    if safety and not errors:
        errors.append(
            "软件急停已锁定，请明确复位"
            if view.robot_state.name == "ESTOP"
            else "机器人故障，请排故后复位"
        )
    headline = view.activity_text if view.active_command else view.headline
    for prefix, text in (
        ("OFFLINE：", ""),
        ("CONNECTED：", ""),
        ("ROBOT_ENABLED：", ""),
        ("TELEOP_RUNNING：", ""),
        ("ESTOP：", "软件急停 · "),
        ("FAULT：", "设备故障 · "),
        ("RECORDING：", "录制中 · "),
        ("PENDING：", "待保存 · "),
        (" frames", " 帧"),
    ):
        headline = headline.replace(prefix, text)
    window.state_headline.setText(headline)
    set_state(window.state_headline, "error" if errors else view.severity)
    connected = ready.robot_connected
    if connected is None:
        connected = view.robot_state.name not in ("OFFLINE", "FAULT", "ESTOP")
    servo_text = {"on": "ON", "off": "OFF"}.get(ready.servo_state, "未知")
    master_ready = (
        ready.master_ready
        if ready.master_ready is not None
        else ready.master_connected and not ready.master_error
    )
    master_text = (
        "故障"
        if ready.master_error
        else "就绪"
        if master_ready
        else "已连接，等待反馈"
        if ready.master_connected
        else "串口已发现"
        if ready.master_discovered
        else "未连接"
    )
    teleop = view.motion_state.name == "TELEOP" and view.workflow_state.name == "TELEOP_RUNNING"
    rec_text = {
        "IDLE": "未录制",
        "RECORDING": "● REC",
        "PENDING": "待处理",
        "SAVING": "保存中",
        "FINALIZING": "发布中",
        "RECOVERING": "恢复中",
    }.get(view.recording_state.name, view.recording_state.name)
    motion_text = {
        "IDLE": "待机",
        "TELEOP": "遥操",
        "REPLAY": "回放",
        "HOME": "回零",
        "POINT_MOVE": "走点",
        "POLICY": "模型控制",
    }.get(view.motion_state.name, view.motion_state.name)
    for widget, text, state in (
        (
            window.robot_badge,
            "Robot · " + ("故障/急停" if safety else "已连接" if connected else "未连接"),
            "error" if safety or ready.robot_error else "success" if connected else "neutral",
        ),
        (
            window.servo_badge,
            "Servo · " + servo_text,
            "success"
            if ready.servo_state == "on" and not ready.robot_error
            else "warning"
            if connected
            else "neutral",
        ),
        (
            window.master_badge,
            f"{ready.master_type.upper() if ready.master_type != 'unknown' else '输入'} · {master_text}",
            "error"
            if ready.master_error
            else "success"
            if master_ready
            else "warning"
            if ready.master_connected
            else "neutral",
        ),
        (
            window.motion_badge,
            "运动 · " + motion_text,
            "success" if view.motion_running else "neutral",
        ),
        (
            window.teleop_badge,
            "Teleop · " + ("运行中" if teleop else "已停止"),
            "success" if teleop else "neutral",
        ),
        (
            window.recording_badge,
            "采集 · " + rec_text,
            "error"
            if view.recording_error
            else "warning"
            if view.episode_pending
            else "success"
            if view.episode_active
            else "neutral",
        ),
    ):
        widget.setText(text)
        set_state(widget, state)
    window.identity_label.setText(ready.robot_name)
    window.identity_label.setToolTip(ready.robot_endpoint or ready.robot_profile)
    name = dataset.get("batch_task") or dataset.get("display_name") or "未创建"
    window.dataset_label.setText(f"Dataset · {name}")
    window.dataset_label.setToolTip(dataset.get("root") or dataset.get("output_root", ""))
    window.episode_label.setText(
        episode_label(dataset, active=view.episode_active or view.episode_pending)
    )
    window.fps_label.setText(f"采集 {dataset.get('quality', {}).get('effective_fps', 0):.1f} FPS")
    window.notification.setText(
        " | ".join(errors)
        or ("正在处理：" + ", ".join(command_activity(c) for c in pending) if pending else "")
    )
    window.notification.setVisible(bool(errors or pending))
    set_state(window.notification, "error" if errors else "info")
    window.summary_status.setText(
        f"Robot {view.robot_state.name} | Servo {servo_text} | {ready.master_type.upper()} {master_text}"
        f" | Motion {view.motion_state.name} | Recording {view.recording_state.name}"
        f" | Fault {'YES' if errors or safety else 'NONE'}"
    )
