"""Trajectory workspaces using snapshots and application commands only."""

from __future__ import annotations

from math import degrees

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHeaderView, QListWidgetItem, QTableWidgetItem, QWidget

from teleop.gello_cr.core.state_machine import Command, WorkflowState

from .generated.ui_trajectory_page import Ui_TrajectoryPanel
from .theme import set_state


class TrajectoryPanel(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._submit = submit
        self._snapshot = {}
        self._context = None
        self._catalog = []
        self._mode = "replay"
        self._ui = Ui_TrajectoryPanel()
        self._ui.setupUi(self)
        self.library_panel = self._ui.trajectory_library_panel
        self.saved_list = self._ui.trajectory_saved_list
        self.record_center = self._ui.trajectory_record_center
        self.replay_center = self._ui.trajectory_replay_center
        self.record_parameters = self._ui.trajectory_record_parameters
        self.replay_parameters = self._ui.trajectory_replay_parameters
        self.record_actions = self._ui.trajectory_record_actions
        self.replay_actions = self._ui.trajectory_replay_actions
        self.record_name = self._ui.trajectory_record_name
        self.record_button = self._ui.trajectory_record_button
        self.finish_button = self._ui.trajectory_finish_button
        self.save_button = self._ui.trajectory_save_button
        self.cancel_button = self._ui.trajectory_cancel_button
        self.refresh_button = self._ui.trajectory_refresh_button
        self.import_json_button = self._ui.trajectory_import_json_button
        self.import_episode_button = self._ui.trajectory_import_episode_button
        self.episode_spin = self._ui.trajectory_episode_spin
        self.mode_combo = self._ui.trajectory_mode_combo
        self.speed_spin = self._ui.trajectory_speed_spin
        self.repeat_spin = self._ui.trajectory_repeat_spin
        self.arm_check = self._ui.trajectory_arm_check
        self.hand_check = self._ui.trajectory_hand_check
        self.preview_button = self._ui.trajectory_preview_button
        self.play_button = self._ui.trajectory_play_button
        self.joint_checks = [getattr(self._ui, f"trajectory_joint_checks_{i}") for i in range(6)]
        self.status_label = self._ui.trajectory_status_label
        self.preview_text = self._ui.trajectory_preview_text
        self.preview_summary = self._ui.trajectory_preview_summary
        self.preview_hint = self._ui.trajectory_preview_hint
        self.preview_warnings = self._ui.trajectory_preview_warnings
        self.joint_table = self._ui.trajectory_joint_table
        self.joint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mode_combo.setItemData(0, "relative")
        self.mode_combo.setItemData(1, "absolute")
        for check in self.joint_checks:
            check.toggled.connect(self._update_enabled)
        for button, command in (
            (self.record_button, Command.START_TRAJECTORY_RECORDING),
            (self.finish_button, Command.STOP_TRAJECTORY_RECORDING),
            (self.save_button, Command.SAVE_TRAJECTORY),
            (self.cancel_button, Command.CANCEL_TRAJECTORY_RECORDING),
        ):
            button.clicked.connect(
                lambda _checked=False, btn=button, cmd=command: self._record_action(btn, cmd)
            )
        self.refresh_button.clicked.connect(lambda: self._submit(Command.LIST_TRAJECTORIES))
        self.preview_button.clicked.connect(self._preview)
        self.play_button.clicked.connect(self._play)
        self.import_json_button.clicked.connect(self._import_json)
        self.import_episode_button.clicked.connect(self._import_episode)
        self.saved_list.currentItemChanged.connect(self._selection_changed)
        self.record_name.textChanged.connect(self._update_enabled)
        self.arm_check.toggled.connect(self._update_enabled)
        self.hand_check.toggled.connect(self._update_enabled)
        self.set_mode("replay")
        self._render_preview()

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """Switch the Designer workspace sections without issuing a command."""
        if mode not in ("record", "replay"):
            raise ValueError(f"Unknown trajectory mode: {mode}")
        self._mode = mode
        index = 0 if mode == "record" else 1
        for stack in (
            self._ui.trajectory_center_stack,
            self._ui.trajectory_parameters_stack,
            self._ui.trajectory_actions_stack,
        ):
            stack.setCurrentIndex(index)
        self._update_enabled()

    def _selected_id(self):
        item = self.saved_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _record_action(self, button, command):
        if self._mode != "record" or not button.isEnabled():
            return
        if command is Command.START_TRAJECTORY_RECORDING:
            self._submit(command, {"name": self.record_name.text().strip()})
        else:
            self._submit(command)

    def _preview(self):
        if self._mode == "replay" and self.preview_button.isEnabled():
            self._submit(Command.PREVIEW_TRAJECTORY, {"trajectory_id": self._selected_id()})

    def _play(self):
        if self._mode != "replay" or not self.play_button.isEnabled():
            return
        self._submit(
            Command.REPLAY_TRAJECTORY,
            {
                "trajectory_id": self._selected_id(),
                "options": {
                    "mode": self.mode_combo.currentData(),
                    "time_scale": self.speed_spin.value(),
                    "repeat": self.repeat_spin.value(),
                    "arm_enabled": self.arm_check.isChecked(),
                    "hand_enabled": self.hand_check.isChecked(),
                    "joint_mask": [check.isChecked() for check in self.joint_checks],
                },
            },
        )

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入旧轨迹", "", "JSON (*.json)", options=QFileDialog.DontUseNativeDialog
        )
        if path:
            self._submit(Command.IMPORT_TRAJECTORY, {"path": path, "source": "legacy_json"})

    def _import_episode(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择 LeRobot 数据集目录", options=QFileDialog.DontUseNativeDialog
        )
        if path:
            self._submit(
                Command.IMPORT_TRAJECTORY,
                {
                    "path": path,
                    "source": "lerobot",
                    "episode_index": self.episode_spin.value(),
                },
            )

    def _selection_changed(self, *_args):
        selected = self._selected_id()
        metadata = next((v for v in self._catalog if v["trajectory_id"] == selected), {})
        mask = metadata.get("joint_mask") or [True] * 6
        for check, enabled in zip(self.joint_checks, mask, strict=True):
            check.blockSignals(True)
            check.setChecked(enabled)
            check.blockSignals(False)
        if "hand_type" in metadata:
            self.hand_check.setChecked(metadata["hand_type"] is not None)
        self._render_preview()
        self._update_enabled()

    def render(self, snapshot, view, readiness, pending=False):
        self._snapshot = snapshot
        self._context = view, readiness, pending
        catalog = snapshot.get("items", [])
        if catalog != self._catalog:
            current = self._selected_id()
            self._catalog = [dict(value) for value in catalog]
            self.saved_list.blockSignals(True)
            self.saved_list.clear()
            selected_row = 0
            for row, value in enumerate(catalog):
                duration = self._metric(value.get("duration_s"), ".2f", " s")
                item = QListWidgetItem(
                    f"{value['name']}\n{value.get('source', '来源未知')} · {duration}"
                )
                item.setData(Qt.UserRole, value["trajectory_id"])
                item.setToolTip(item.text())
                self.saved_list.addItem(item)
                if value["trajectory_id"] == current:
                    selected_row = row
            self.saved_list.setCurrentRow(selected_row if catalog else -1)
            self.saved_list.blockSignals(False)
            self._ui.trajectory_library_count.setText(f"{len(catalog)} 条轨迹")
            self._selection_changed()
        count, duration = snapshot.get("frame_count", 0), snapshot.get("duration_s", 0.0)
        recording = bool(snapshot.get("recording"))
        unsaved = bool(count) or bool(snapshot.get("pending"))
        state = "正在录制" if recording else "待保存" if unsaved else "准备录制"
        self.status_label.setText(
            snapshot.get("recording_error") or f"{state} · {count} 帧 · {duration:.2f} s"
        )
        self._ui.trajectory_record_indicator.setText(f"● REC · {state}" if recording else state)
        set_state(
            self._ui.trajectory_record_indicator,
            "success" if recording else "warning" if unsaved else "neutral",
        )
        self._ui.trajectory_frames_value.setText(str(count))
        self._ui.trajectory_elapsed_value.setText(f"{duration:.2f} s")
        self._ui.trajectory_record_context.setText(
            "正在采集机器人与 Hand 的状态或指令，可继续操作当前控制流程。"
            if recording
            else "本次记录尚未保存。停止并保存，或在保存失败后重试。"
            if unsaved
            else "输入名称后开始记录。采集当前控制流程中的机器人与 Hand 状态或指令。"
        )
        self._render_preview()
        self._update_enabled()

    def _update_enabled(self):
        if self._context is None:
            for button in (
                self.record_button,
                self.finish_button,
                self.save_button,
                self.cancel_button,
                self.preview_button,
                self.play_button,
            ):
                button.setEnabled(False)
            return
        view, readiness, busy = self._context
        state = view.workflow_state
        recording = bool(self._snapshot.get("recording"))
        playing = bool(self._snapshot.get("playing")) or state is WorkflowState.REPLAY_RUNNING
        unsaved = (
            recording or bool(self._snapshot.get("frame_count")) or self._snapshot.get("pending")
        )
        record_mode, replay_mode = self._mode == "record", self._mode == "replay"
        record_allowed = view.actions.get(Command.START_TRAJECTORY_RECORDING, False)
        self.record_button.setEnabled(
            record_mode
            and record_allowed
            and not busy
            and not unsaved
            and bool(self.record_name.text().strip())
        )
        self.finish_button.setEnabled(
            record_mode and bool(unsaved) and not self._snapshot.get("pending") and not busy
        )
        self.save_button.setEnabled(
            record_mode and bool(self._snapshot.get("pending")) and not busy
        )
        self.cancel_button.setEnabled(record_mode and bool(unsaved) and not busy)
        self.record_name.setEnabled(record_mode and not unsaved and not busy)
        selected = self._selected_id() is not None
        arm, hand = self.arm_check.isChecked(), self.hand_check.isChecked()
        replay_allowed = view.actions.get(Command.REPLAY_TRAJECTORY, False)
        self.play_button.setEnabled(
            replay_mode
            and replay_allowed
            and selected
            and not busy
            and not unsaved
            and (arm or hand)
            and (not arm or any(c.isChecked() for c in self.joint_checks))
            and (not hand or readiness.o6_connected)
            and not view.episode_pending
        )
        editable = not busy and not playing and not unsaved
        for widget in (
            self.mode_combo,
            self.speed_spin,
            self.repeat_spin,
            self.arm_check,
            self.hand_check,
        ):
            widget.setEnabled(replay_mode and editable)
        for widget in (
            self.saved_list,
            self.import_json_button,
            self.import_episode_button,
            self.episode_spin,
            self.refresh_button,
        ):
            widget.setEnabled(editable)
        for check in self.joint_checks:
            check.setEnabled(replay_mode and editable and arm)
        self.preview_button.setEnabled(replay_mode and selected and editable)

    @staticmethod
    def _metric(value, spec, suffix=""):
        return f"{value:{spec}}{suffix}" if value is not None else "—"

    def _render_preview(self):
        selected = self._selected_id()
        metadata = next((v for v in self._catalog if v["trajectory_id"] == selected), {})
        preview = self._snapshot.get("preview") or {}
        if preview.get("trajectory_id") != selected or selected is None:
            preview = {}
        info = {**metadata, **preview}
        if selected is None:
            self.preview_summary.setText("选择轨迹以查看预览")
            self.preview_hint.setText("从左侧轨迹库选择一条轨迹，然后点击“读取预览”。")
        else:
            self.preview_summary.setText(
                f"{info.get('name', '—')} · {info.get('robot_type', '机器人类型未知')}\n"
                f"来源 {info.get('source', '—')} · "
                f"{self._metric(info.get('duration_s'), '.2f', ' s')} · "
                f"{self._metric(info.get('frame_count'), 'd', ' 帧')} · "
                f"{self._metric(info.get('fps'), '.1f', ' Hz')}"
            )
            self.preview_hint.setText(
                "已读取轨迹统计。关节角度单位为 °，速度为 °/s；此处显示整条轨迹的汇总。"
                if preview
                else "已选择轨迹。点击“读取预览”查看起终点、关节范围、速度与帧间步长。"
            )
        warnings = "\n".join(preview.get("warnings", ()))
        self.preview_warnings.setText(warnings)
        self.preview_warnings.setVisible(bool(warnings))
        has_joints = bool(preview.get("joint_range_rad"))
        vectors = (
            preview.get("start_joint_rad"),
            preview.get("end_joint_rad"),
            preview.get("joint_range_rad"),
            preview.get("max_joint_velocity_rad_s"),
            preview.get("max_joint_delta_rad"),
        )
        for row in range(6):
            for column, vector in enumerate(vectors):
                text = "—"
                if has_joints and vector is not None:
                    value = vector[row]
                    if column == 2:
                        text = f"{degrees(value[0]):.2f} ～ {degrees(value[1]):.2f}"
                    else:
                        text = f"{degrees(value):.2f}"
                    text = text.replace("-", "−")
                item = self.joint_table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignCenter)
                    self.joint_table.setItem(row, column, item)
                item.setText(text)
                item.setToolTip(text)
        self._ui.trajectory_tcp_hand_info.setText(self._tcp_hand_info(preview))
        text = self._preview_details(preview) if preview else ""
        if self.preview_text.toPlainText() != text:
            self.preview_text.setPlainText(text)

    @staticmethod
    def _tcp_hand_info(preview):
        if not preview:
            return "TCP / Hand：读取预览后显示可用范围。"
        tcp, hand = preview.get("tcp_range"), preview.get("hand_range")
        tcp_text = (
            "；".join(
                f"{axis} {low:.4g}～{high:.4g} {unit}"
                for (low, high), axis, unit in zip(
                    tcp,
                    ("X", "Y", "Z", "Rx", "Ry", "Rz"),
                    ("m",) * 3 + ("rad",) * 3,
                    strict=True,
                )
            )
            if tcp
            else "无可用数据"
        )
        hand_text = (
            "；".join(f"H{i + 1} {low:.4g}～{high:.4g}" for i, (low, high) in enumerate(hand))
            if hand
            else "无可用数据"
        )
        return f"TCP 范围：{tcp_text}\nHand 范围（原始位置单位）：{hand_text}"

    @staticmethod
    def _preview_details(preview):
        def values(vector):
            return "无" if vector is None else ", ".join(f"{v:.4g}" for v in vector)

        def ranges(bounds):
            return "无" if bounds is None else "; ".join(f"{a:.4g}～{b:.4g}" for a, b in bounds)

        return (
            f"{preview['name']} · {preview['robot_type']} · {preview['frame_count']} 帧 · "
            f"{preview['duration_s']:.2f}s · {preview['fps']:.1f}Hz\n"
            f"来源：{preview.get('source', '—')} · 创建：{preview.get('created_at', '—')}\n"
            f"关节范围 rad：{ranges(preview.get('joint_range_rad'))}\n"
            f"最大帧间变化 rad：{values(preview.get('max_joint_delta_rad'))}\n"
            f"最大关节速度 rad/s：{values(preview.get('max_joint_velocity_rad_s'))}\n"
            f"起点 rad：{values(preview.get('start_joint_rad'))}\n"
            f"终点 rad：{values(preview.get('end_joint_rad'))}\n"
            f"TCP 范围 m/rad：{ranges(preview.get('tcp_range'))}\n"
            f"Hand 范围：{ranges(preview.get('hand_range'))}\n"
            + "\n".join(preview.get("warnings", ()))
        )
