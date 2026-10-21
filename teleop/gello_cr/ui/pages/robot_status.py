"""Readable robot readiness and explicitly sampled positions, without device I/O."""

import json
import math
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidgetItem, QWidget

from teleop.gello_cr.core.state_machine import Command, RobotState

from ..generated.ui_robot_status_page import Ui_RobotStatusPage
from ..theme import set_state

_MOTION = {
    "IDLE": "待机",
    "TELEOP": "遥操跟随",
    "REPLAY": "轨迹回放",
    "HOME": "返回 HOME",
    "POINT_MOVE": "走点执行",
    "POLICY": "模型控制",
}
_RECORDING = {
    "IDLE": "未录制",
    "RECORDING": "● REC · 正在录制",
    "PENDING": "待保存 / 丢弃",
    "SAVING": "正在保存",
    "FINALIZING": "正在发布数据集",
    "RECOVERING": "正在恢复数据",
}


class RobotStatusPage(QWidget):
    connection_requested = Signal()

    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._ui = Ui_RobotStatusPage()
        self._ui.setupUi(self)
        for name in (
            "connection_value",
            "servo_value",
            "motion_value",
            "master_value",
            "hand_value",
            "recording_value",
            "fault_banner",
            "fault_hint",
            "fault_code",
            "feedback_hint",
            "joint_table",
            "tcp_table",
            "details",
            "details_toggle",
            "technical_panel",
            "copy_details_button",
            "connection_button",
            "refresh_button",
            "reset_fault_button",
            "reset_estop_button",
        ):
            setattr(self, name, getattr(self._ui, "robot_" + name))
        for table in (self.joint_table, self.tcp_table):
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.connection_button.clicked.connect(self.connection_requested)
        self.details_toggle.toggled.connect(self._show_technical)
        self.copy_details_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.details.toPlainText())
        )
        self._show_technical(False)
        for button, command in (
            (self.refresh_button, Command.REFRESH_ROBOT_STATUS),
            (self.reset_fault_button, Command.RESET_FAULT),
            (self.reset_estop_button, Command.RESET_ESTOP),
        ):
            button.clicked.connect(lambda checked=False, cmd=command: submit(cmd))

    def _show_technical(self, visible):
        self.technical_panel.setVisible(visible)
        self.details_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)

    @staticmethod
    def _value(label, text, state):
        label.setText(text)
        set_state(label, state)

    def render(self, view, readiness, diagnostics, busy=False):
        connected = readiness.robot_connected
        if connected is None:
            connected = (
                False
                if view.robot_state is RobotState.OFFLINE
                else True
                if view.robot_state in (RobotState.CONNECTED, RobotState.ENABLED)
                else None
            )
        self._ui.robot_identity_label.setText(readiness.robot_name)
        self._ui.robot_endpoint_label.setText(
            readiness.robot_endpoint
            or "硬件配置："
            + (readiness.robot_profile or diagnostics.get("hardware_profile") or "未选择")
        )
        self.connection_button.setText("前往数据采集" if connected else "前往设备连接")
        self._value(
            self.connection_value,
            "已连接" if connected else "未连接" if connected is False else "未确认",
            "error" if readiness.robot_error else "success" if connected else "neutral",
        )
        servo = readiness.servo_state
        servo_text, servo_style = {
            "on": ("ON · 已使能", "success"),
            "off": ("OFF · 未使能", "warning"),
            "error": ("报警 · 请排查", "error"),
        }.get(servo, ("未确认", "warning"))
        if connected is False:
            servo_text, servo_style = "未连接", "neutral"
        self._value(self.servo_value, servo_text, servo_style)
        self._value(
            self.motion_value,
            _MOTION[view.motion_state.name],
            "success" if view.motion_running else "neutral",
        )
        master_ready = (
            readiness.master_connected if readiness.master_ready is None else readiness.master_ready
        )
        master_text = (
            "异常"
            if readiness.master_error
            else "就绪"
            if master_ready and readiness.master_connected
            else "已连接，等待反馈"
            if readiness.master_connected
            else "已发现，未连接"
            if readiness.master_discovered
            else "未连接"
        )
        prefix = readiness.master_type.upper() if readiness.master_type != "unknown" else "输入设备"
        self._value(
            self.master_value,
            f"{prefix} · {master_text}",
            "error"
            if readiness.master_error
            else "success"
            if master_ready and readiness.master_connected
            else "warning"
            if readiness.master_discovered or readiness.master_connected
            else "neutral",
        )
        hand_ready = (
            readiness.o6_connected if readiness.hand_ready is None else readiness.hand_ready
        )
        hand_text = (
            "异常"
            if readiness.o6_error
            else "就绪"
            if hand_ready and readiness.o6_connected
            else "已连接，等待反馈"
            if readiness.o6_connected
            else "未连接"
            if readiness.hand_required
            else "非必需，未连接"
        )
        self._value(
            self.hand_value,
            hand_text,
            "error"
            if readiness.o6_error
            else "success"
            if hand_ready and readiness.o6_connected
            else "warning"
            if readiness.o6_connected
            else "neutral",
        )
        self._value(
            self.recording_value,
            _RECORDING[view.recording_state.name],
            "error"
            if view.recording_error
            else "success"
            if view.episode_active
            else "warning"
            if view.episode_pending
            else "neutral",
        )
        errors = []
        seen = set()
        for source, message in (
            ("机器人", readiness.robot_error),
            ("运动", view.runtime_error),
            ("操作", view.application_error),
            ("遥操输入", readiness.master_error),
            ("末端", readiness.o6_error),
            ("相机", readiness.camera_error),
            ("采集", view.recording_error),
        ):
            if message and message not in seen:
                errors.append(f"{source}：{message}")
                seen.add(message)
        safety = view.robot_state in (RobotState.FAULT, RobotState.ESTOP)
        if safety and not errors:
            errors.append(
                "软件急停已锁定" if view.robot_state is RobotState.ESTOP else "机器人故障已锁定"
            )
        self.fault_banner.setText("\n".join(errors))
        self.fault_banner.setVisible(bool(errors))
        set_state(self.fault_banner, "error" if errors else "neutral")
        if safety and (view.episode_active or view.episode_pending):
            hint = "当前 Episode 尚未处理：先保存为失败或明确丢弃，再排故并复位；复位后保持停止。"
        elif view.robot_state is RobotState.ESTOP:
            hint = "确认现场允许解除软件急停后再操作；解除后保持停止，需要手动重新启动运动。"
        elif safety or errors:
            hint = "先处理上方异常，再按允许的操作复位；复位后保持停止。"
        elif connected is False:
            hint = "先前往设备连接，确认机器人与 Servo 状态；连接后可读取关节与 TCP 反馈。"
        else:
            hint = "当前未收到故障报告。位置为手动读取的快照，运动后请重新读取。"
        self.fault_hint.setText(hint)
        self.fault_hint.setVisible(True)
        code = diagnostics.get("fault_code")
        self.fault_code.setVisible(code is not None)
        self.fault_code.setText(f"上次读取故障码：{code}")
        self._render_positions(connected, diagnostics)
        for button, command in (
            (self.refresh_button, Command.REFRESH_ROBOT_STATUS),
            (self.reset_fault_button, Command.RESET_FAULT),
            (self.reset_estop_button, Command.RESET_ESTOP),
        ):
            button.setEnabled(view.actions.get(command, False) and not busy)
            button.setToolTip(
                "正在处理上一项请求，请稍候。" if busy else view.action_reasons.get(command, "")
            )
        technical = self._diagnostic_text(view, readiness, diagnostics, errors)
        if self.details.toPlainText() != technical:
            self.details.setPlainText(technical)

    def _render_positions(self, connected, diagnostics):
        sampled_at = diagnostics.get("sampled_at")
        usable = connected is True and bool(sampled_at)
        joints = diagnostics.get("joint_rad") if usable else None
        tcp = diagnostics.get("tcp") if usable else None
        unknown = "未连接" if connected is False else "未读取" if connected else "未确认连接"
        joint_count = len(joints) if joints else 6
        self.joint_table.setRowCount(joint_count)
        self._fill_table(
            self.joint_table,
            [f"J{i + 1}" for i in range(joint_count)],
            joints,
            [180 / math.pi] * joint_count,
            unknown,
        )
        self._fill_table(
            self.tcp_table,
            ["X (mm)", "Y (mm)", "Z (mm)", "Rx (°)", "Ry (°)", "Rz (°)"],
            tcp,
            [1000] * 3 + [180 / math.pi] * 3,
            unknown,
        )
        if connected is False:
            hint = "机器人未连接，位置未确认。"
        elif not usable:
            hint = "尚未读取位置快照；点击“读取机器人反馈”更新。"
        else:
            age = max(0.0, time.monotonic() - sampled_at)
            hint = f"位置快照 · {age:.1f} 秒前读取；不是实时位置，运动后请重新读取。"
        self.feedback_hint.setText(hint)

    @staticmethod
    def _fill_table(table, names, values, scales, unknown):
        for row, (name, scale) in enumerate(zip(names, scales, strict=True)):
            value = values[row] if values is not None else None
            text = unknown if value is None else f"{value * scale:.3f}"
            for column, content in enumerate((name, text)):
                item = table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(
                        Qt.AlignLeft | Qt.AlignVCenter
                        if column == 0
                        else Qt.AlignRight | Qt.AlignVCenter
                    )
                    table.setItem(row, column, item)
                item.setText(content)

    def _diagnostic_text(self, view, readiness, diagnostics, errors):
        lines = [
            f"软件版本：{diagnostics.get('version', '未提供')}",
            f"代码版本：{diagnostics.get('git_commit', '未提供')}",
            f"Python：{diagnostics.get('python', '未提供')}",
            f"Python 路径：{diagnostics.get('python_executable', '未提供')}",
            f"硬件配置：{readiness.robot_profile or diagnostics.get('hardware_profile', '未提供')}",
            f"机器人：{readiness.robot_name} · {self.connection_value.text()}",
            f"连接地址：{readiness.robot_endpoint or '未提供'}",
            f"Servo：{self.servo_value.text()}（上次手动读取 SDK 值：{diagnostics.get('servo_state', '未读取')}）",
            f"运动：{self.motion_value.text()} / {view.workflow_state.name}",
            f"输入：{self.master_value.text()}",
            f"末端：{self.hand_value.text()}",
            f"采集：{self.recording_value.text()}",
            f"位置读取时间（monotonic）：{diagnostics.get('sampled_at', '未读取')}",
            "关节 rad：" + json.dumps(diagnostics.get("joint_rad"), ensure_ascii=False),
            "TCP m/rad：" + json.dumps(diagnostics.get("tcp"), ensure_ascii=False),
            "故障码：" + str(diagnostics.get("fault_code", "设备未提供")),
            "异常：\n" + ("\n".join(errors) or "当前未收到故障报告"),
            "Dataset 设置：\n"
            + json.dumps(diagnostics.get("dataset", {}), ensure_ascii=False, indent=2),
        ]
        return "\n".join(lines)
