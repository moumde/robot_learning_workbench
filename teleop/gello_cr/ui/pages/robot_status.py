"""Read-only diagnostics and explicit refresh/reset commands."""

import math
import time

from PySide6.QtWidgets import QWidget

from teleop.gello_cr.core.state_machine import Command

from ..generated.ui_robot_status_page import Ui_RobotStatusPage


class RobotStatusPage(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._ui = Ui_RobotStatusPage()
        self._ui.setupUi(self)
        self.details = self._ui.robot_details
        self.refresh_button = self._ui.robot_refresh_button
        self.reset_fault_button = self._ui.robot_reset_fault_button
        self.reset_estop_button = self._ui.robot_reset_estop_button
        for button, cmd in (
            (self.refresh_button, Command.REFRESH_ROBOT_STATUS),
            (self.reset_fault_button, Command.RESET_FAULT),
        ):
            button.clicked.connect(lambda checked=False, command=cmd: submit(command))
        self.reset_estop_button.clicked.connect(lambda: submit(Command.RESET_ESTOP))

    def render(self, view, readiness, diagnostics, busy=False):
        def numbers(values, scale):
            return "未读取" if values is None else ", ".join(f"{v * scale:.3f}" for v in values)

        master = "CONNECTED" if readiness.master_connected else "OFFLINE"
        text = (
            f"Workbench: {diagnostics.get('version', 'unknown')} · "
            f"git {diagnostics.get('git_commit', 'unknown')[:12]}\n"
            f"Python: {diagnostics.get('python', 'unknown')} · "
            f"Profile: {diagnostics.get('hardware_profile', 'unknown')}\n"
            f"Robot: {view.robot_state.name}\nMotion owner: {view.motion_state.name}\n"
            f"Recording: {view.recording_state.name}\n"
            f"Servo state: {diagnostics.get('servo_state', '未读取')}\n"
            f"Control source: {readiness.master_type} · {master}\n"
            f"O6: {'CONNECTED' if readiness.o6_connected else 'OFFLINE'}\n"
            f"Joint °: {numbers(diagnostics.get('joint_rad'), 180 / math.pi)}\n"
        )
        text += f"Dataset: {diagnostics.get('dataset', {})}\n"
        tcp = diagnostics.get("tcp")
        text += f"TCP mm: {numbers(tcp[:3] if tcp else None, 1000)}\n"
        text += f"TCP °: {numbers(tcp[3:] if tcp else None, 180 / math.pi)}\n"
        if diagnostics.get("sampled_at"):
            text += (
                f"反馈时龄: {time.monotonic() - diagnostics['sampled_at']:.2f}s（点击读取更新）\n"
            )
        if diagnostics.get("last_command_at"):
            age_ms = (time.monotonic() - diagnostics["last_command_at"]) * 1000
            text += f"最近命令时龄: {age_ms:.0f} ms\n"
        text += "\nFault code: " + str(diagnostics.get("fault_code", "设备未提供"))
        text += "\nFault source / message:\n" + (
            "Runtime: " + view.runtime_error
            if view.runtime_error
            else "Application: " + view.application_error
            if view.application_error
            else "无"
        )
        text += (
            "\n遥操设备: "
            + (readiness.master_error or "无错误")
            + "\nO6: "
            + (readiness.o6_error or "无错误")
        )
        if self.details.toPlainText() != text:
            self.details.setPlainText(text)
        self.refresh_button.setEnabled(view.robot_state.name != "OFFLINE" and not busy)
        self.reset_fault_button.setEnabled(view.actions[Command.RESET_FAULT] and not busy)
        self.reset_estop_button.setEnabled(view.actions[Command.RESET_ESTOP] and not busy)
