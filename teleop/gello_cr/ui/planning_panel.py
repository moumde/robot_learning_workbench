"""Point and waypoint editor: commands and read-only previews, without device I/O."""

from __future__ import annotations

import math

from PySide6.QtWidgets import QTableWidgetItem, QWidget

from teleop.gello_cr.core.state_machine import Command, MotionState, WorkflowState

from .generated.ui_planning_page import Ui_PlanningPanel


class PlanningPanel(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._submit = submit
        self._snapshot = {}
        self._context = None
        self._revision = 0
        self._planned_revision = None
        self._requested_revision = None
        self._previous_plan_id = None
        self._position_serial = 0
        self._add_current_pending = False
        self._configured = False
        self._ui = Ui_PlanningPanel()
        self._ui.setupUi(self)
        self.mode_combo = self._ui.planning_mode_combo
        self.name_edit = self._ui.planning_name_edit
        self.speed_spin = self._ui.planning_speed_spin
        self.offline_start = self._ui.planning_offline_start
        self.target_spins = [
            self._ui.planning_target_spins_0,
            self._ui.planning_target_spins_1,
            self._ui.planning_target_spins_2,
            self._ui.planning_target_spins_3,
            self._ui.planning_target_spins_4,
            self._ui.planning_target_spins_5,
        ]
        self.target_labels = [
            self._ui.planning_target_labels_0,
            self._ui.planning_target_labels_1,
            self._ui.planning_target_labels_2,
            self._ui.planning_target_labels_3,
            self._ui.planning_target_labels_4,
            self._ui.planning_target_labels_5,
        ]
        self.table = self._ui.planning_table
        self.read_button = self._ui.planning_read_button
        self.add_current_button = self._ui.planning_add_current_button
        self.add_button = self._ui.planning_add_button
        self.delete_button = self._ui.planning_delete_button
        self.up_button = self._ui.planning_up_button
        self.down_button = self._ui.planning_down_button
        self.plan_button = self._ui.planning_plan_button
        self.execute_button = self._ui.planning_execute_button
        self.save_button = self._ui.planning_save_button
        self.status_label = self._ui.planning_status_label
        self.preview_text = self._ui.planning_preview_text
        self.editor_tabs = self._ui.planning_editor_tabs
        self.parameter_panel = self._ui.planning_parameter_panel
        self.waypoint_panel = self._ui.planning_waypoint_panel
        self.action_bar = self._ui.planning_action_bar
        self.result_state = self._ui.planning_result_state
        self.result_summary = self._ui.planning_result_summary
        self._ui.planning_mode_combo.setItemData(0, "joint")
        self._ui.planning_mode_combo.setItemData(1, "tcp_ptp")
        self._ui.planning_mode_combo.setItemData(2, "tcp_linear")
        self._ui.planning_mode_combo.setItemData(3, "waypoints")
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._changed)
        self.offline_start.textChanged.connect(self._changed)
        for spin in self.target_spins:
            spin.valueChanged.connect(self._changed)
        self.read_button.clicked.connect(lambda: self._read(False))
        self.add_current_button.clicked.connect(lambda: self._read(True))
        self.add_button.clicked.connect(self._add)
        self.delete_button.clicked.connect(self._delete)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.plan_button.clicked.connect(self._plan)
        self.execute_button.clicked.connect(
            lambda: self._submit(Command.EXECUTE_PLAN, {"plan_id": self._snapshot["plan_id"]})
        )
        self.save_button.clicked.connect(
            lambda: self._submit(Command.SAVE_MOTION_PLAN, {"plan_id": self._snapshot["plan_id"]})
        )
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.name_edit.textChanged.connect(self._changed)
        self.speed_spin.valueChanged.connect(self._changed)
        self._mode_changed()
        self.execute_button.setEnabled(False)
        self.save_button.setEnabled(False)

    def _changed(self, *args):
        self._revision += 1
        self._update_enabled()

    def _mode_changed(self, *args):
        joint = self.mode_combo.currentData() == "joint"
        for label, text in zip(
            self.target_labels,
            [f"J{i + 1} °" for i in range(6)]
            if joint
            else ["X mm", "Y mm", "Z mm", "Rx °", "Ry °", "Rz °"],
            strict=True,
        ):
            label.setText(text)
        waypoints = self.mode_combo.currentData() == "waypoints"
        self.waypoint_panel.setVisible(waypoints)
        self.table.setVisible(waypoints)
        self.add_current_button.setVisible(waypoints)
        self._ui.planning_target_group.setTitle("目标关节" if joint else "目标 TCP")
        self._ui.planning_target_help.setText(
            "Joint：输入六个关节角，单位 °。"
            if joint
            else "TCP：位置单位 mm，姿态单位 °。"
            + ("\n将目标添加到列表，再按行编辑运动方式、速度与停留。" if waypoints else "")
        )
        self._changed()

    def _read(self, add):
        self._add_current_pending = add
        self._submit(Command.READ_MOTION_POSITION)

    def _add(self):
        self._append([spin.value() for spin in self.target_spins] + ["linear", 100, 0])

    def _append(self, values):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.table.selectRow(row)
        self._changed()

    def _delete(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._changed()

    def _move(self, offset):
        row = self.table.currentRow()
        other = row + offset
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        for column in range(self.table.columnCount()):
            first, second = self.table.takeItem(row, column), self.table.takeItem(other, column)
            self.table.setItem(row, column, second)
            self.table.setItem(other, column, first)
        self.table.selectRow(other)
        self._changed()

    @staticmethod
    def _tcp(values):
        return [v / 1000 for v in values[:3]] + [math.radians(v) for v in values[3:]]

    def _plan(self):
        kind = self.mode_combo.currentData()
        payload = {
            "kind": kind,
            "name": self.name_edit.text(),
            "speed_scale": self.speed_spin.value() / 100,
        }
        try:
            values = [spin.value() for spin in self.target_spins]
            payload["target"] = (
                [math.radians(v) for v in values] if kind == "joint" else self._tcp(values)
            )
            if kind == "waypoints":
                payload["waypoints"] = []
                for row in range(self.table.rowCount()):
                    values = [self.table.item(row, col).text() for col in range(9)]
                    mode = values[6].strip().lower()
                    if mode not in ("ptp", "linear"):
                        raise ValueError("Waypoint Mode 需要 ptp 或 linear")
                    payload["waypoints"].append(
                        {
                            "pose": self._tcp([float(v) for v in values[:6]]),
                            "mode": mode,
                            "speed_scale": float(values[7]) / 100,
                            "hold_time_s": float(values[8]),
                        }
                    )
            if self._context and self._context[0].robot_state.name == "OFFLINE":
                start = [float(v.strip()) for v in self.offline_start.text().split(",")]
                if len(start) != 6:
                    raise ValueError("离线起点需要六个角度")
                payload["start_joint_rad"] = [math.radians(v) for v in start]
            self._planned_revision = None
            self._requested_revision = self._revision
            self._previous_plan_id = self._snapshot.get("plan_id")
            self._submit(Command.PLAN_MOTION, payload)
        except (ValueError, AttributeError) as exc:
            self.status_label.setText(f"输入错误：{exc}")
            self._planned_revision = self._requested_revision = None
        self._update_enabled()

    def render(self, snapshot, view, busy=False):
        self._snapshot = dict(snapshot)
        self._context = view, busy
        plan_id = snapshot.get("plan_id")
        if self._requested_revision is not None and plan_id and plan_id != self._previous_plan_id:
            self._planned_revision = self._requested_revision
            self._requested_revision = None
        if not self._configured and snapshot:
            self.speed_spin.setValue(float(snapshot.get("default_speed_scale", 0.3)) * 100)
            self._configured = True
        serial = snapshot.get("position_serial", 0)
        if serial != self._position_serial:
            self._position_serial = serial
            position = snapshot.get("position")
            if position:
                joint = self.mode_combo.currentData() == "joint"
                values = (
                    [math.degrees(v) for v in position["joint_rad"]]
                    if joint
                    else (
                        [v * 1000 for v in position["tcp"][:3]]
                        + [math.degrees(v) for v in position["tcp"][3:]]
                    )
                )
                for spin, value in zip(self.target_spins, values, strict=True):
                    spin.setValue(value)
                if self._add_current_pending:
                    self._append(values + ["linear", 100, 0])
                self._add_current_pending = False
        preview = snapshot.get("preview") or {}
        metrics = snapshot.get("metrics") or {}

        def numbers(values):
            return "无" if values is None else ", ".join(f"{v:.4g}" for v in values)

        status = snapshot.get("status", "IDLE")
        error = str(snapshot.get("error") or "")
        text = ""
        if error:
            label = "规划失败" if status == "PLANNING_FAILED" else "错误"
            text = f"{label}：{error}\n\n"
        if preview.get("collision_checking", "unavailable") == "unavailable":
            text += "说明：路径碰撞预检：未实现（未验证自碰撞或环境障碍物）\n"
        else:
            text += "说明：路径碰撞预检：状态未确认（未确认自碰撞或环境障碍物检查）\n"
        if preview:
            text += (
                f"{metrics.get('frame_count', 0)} 帧 · {metrics.get('duration_s', 0):.3f}s\n"
                f"起始 Joint rad：{numbers(preview.get('start_joint_rad'))}\n"
                f"目标 Joint rad：{numbers(preview.get('target_joint_rad'))}\n"
                f"起始 TCP m/rad：{numbers(preview.get('start_pose'))}\n"
                f"目标 TCP m/rad：{numbers(preview.get('target_pose'))}\n"
                f"最大 Joint 速度：{metrics.get('max_joint_velocity', 0):.4g} rad/s · "
                f"加速度：{metrics.get('max_joint_acceleration', 0):.4g} rad/s² · "
                f"帧间变化：{metrics.get('max_joint_delta', 0):.4g} rad\n"
                f"TCP 路径长度：{metrics.get('path_length_tcp_m')} m\n"
            )
        text += "\n".join(snapshot.get("warnings", ()))
        if snapshot.get("saved_path"):
            text += "\n已保存：" + snapshot["saved_path"]
        if self.preview_text.toPlainText() != text:
            self.preview_text.setPlainText(text)
        if self._planned_revision != self._revision and preview:
            status += " · 输入已修改，请重新规划"
        self.status_label.setText(status)
        self._update_enabled()

    def _update_result_summary(self):
        preview = self._snapshot.get("preview") or {}
        metrics = self._snapshot.get("metrics") or {}
        status = self._snapshot.get("status", "IDLE")
        error = self._snapshot.get("error")
        if error:
            label = "规划失败" if status == "PLANNING_FAILED" else "错误"
            self.result_state.setText(f"{label}：{error}")
        elif status == "PLANNING_FAILED":
            self.result_state.setText("规划失败 · 请查看规划结果")
        elif status == "PLANNING":
            self.result_state.setText("正在生成规划…")
        elif preview and self._planned_revision != self._revision:
            self.result_state.setText("输入已修改，请重新规划")
        elif preview:
            self.result_state.setText(
                "正在执行规划" if self._snapshot.get("running") else "规划结果已生成"
            )
        else:
            self.result_state.setText("等待生成规划")
        if preview:
            summary = f"{metrics.get('frame_count', 0)} 帧 · {metrics.get('duration_s', 0):.3f} s"
            path_length = metrics.get("path_length_tcp_m")
            if path_length is not None:
                summary += f" · TCP 路径 {path_length:.4g} m"
            self.result_summary.setText(summary)
        else:
            self.result_summary.setText("编辑目标后生成规划，可查看实际帧数、时长与端点。")
        unavailable = preview.get("collision_checking", "unavailable") == "unavailable"
        self._ui.planning_collision_notice.setText(
            "路径碰撞预检：未实现（未验证自碰撞或环境障碍物）。"
            if unavailable
            else "路径碰撞预检：状态未确认（未确认自碰撞或环境障碍物检查）。"
        )

    def _update_enabled(self):
        self._update_result_summary()
        if self._context is None:
            return
        view, busy = self._context
        running = (
            self._snapshot.get("running")
            or view.workflow_state
            in (
                WorkflowState.POINT_MOVE_RUNNING,
                WorkflowState.REPLAY_RUNNING,
                WorkflowState.RETURNING_HOME,
                WorkflowState.DAGGER_RUNNING,
            )
            or view.motion_state
            in (MotionState.REPLAY, MotionState.POINT_MOVE, MotionState.HOME, MotionState.POLICY)
        )
        editable = not busy and not running
        waypoints = self.mode_combo.currentData() == "waypoints"
        for widget in (
            self.mode_combo,
            self.name_edit,
            self.speed_spin,
            self.table,
            *self.target_spins,
        ):
            widget.setEnabled(editable)
        available = view.workflow_state in (
            WorkflowState.CONNECTED,
            WorkflowState.ROBOT_ENABLED,
            WorkflowState.TELEOP_RUNNING,
        )
        self.read_button.setEnabled(editable and available)
        for button in (
            self.add_current_button,
            self.add_button,
            self.delete_button,
            self.up_button,
            self.down_button,
        ):
            button.setEnabled(
                editable and waypoints and (available or button is not self.add_current_button)
            )
        offline = view.robot_state.name == "OFFLINE"
        self._ui.planning_offline_panel.setVisible(offline)
        self.offline_start.setVisible(offline)
        self.offline_start.setEnabled(editable)
        self.offline_start.setPlaceholderText("离线起点 J1–J6，单位 °")
        self.plan_button.setEnabled(
            editable
            and view.actions.get(Command.PLAN_MOTION, False)
            and (available or offline and self.mode_combo.currentData() == "joint")
        )
        valid = bool(self._snapshot.get("plan_id")) and self._planned_revision == self._revision
        self.execute_button.setEnabled(
            valid and editable and view.actions.get(Command.EXECUTE_PLAN, False)
        )
        self.save_button.setEnabled(valid and editable)
