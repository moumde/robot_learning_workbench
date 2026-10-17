"""Trajectory controls using snapshots and application commands only."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QWidget

from gello_cr.core.state_machine import Command, WorkflowState

from .generated.ui_trajectory_page import Ui_TrajectoryPanel


class TrajectoryPanel(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._submit = submit
        self._snapshot = {}
        self._context = None
        self._catalog = []
        self._ui = Ui_TrajectoryPanel()
        self._ui.setupUi(self)
        self.record_name = self._ui.trajectory_record_name
        self.record_button = self._ui.trajectory_record_button
        self.finish_button = self._ui.trajectory_finish_button
        self.save_button = self._ui.trajectory_save_button
        self.cancel_button = self._ui.trajectory_cancel_button
        self.saved_combo = self._ui.trajectory_saved_combo
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
        self.joint_checks = [
            self._ui.trajectory_joint_checks_0,
            self._ui.trajectory_joint_checks_1,
            self._ui.trajectory_joint_checks_2,
            self._ui.trajectory_joint_checks_3,
            self._ui.trajectory_joint_checks_4,
            self._ui.trajectory_joint_checks_5,
        ]
        self.status_label = self._ui.trajectory_status_label
        self.preview_text = self._ui.trajectory_preview_text
        self._ui.trajectory_mode_combo.setItemData(0, "relative")
        self._ui.trajectory_mode_combo.setItemData(1, "absolute")
        for check in self.joint_checks:
            check.toggled.connect(self._update_enabled)

        self.record_button.clicked.connect(
            lambda: self._submit(
                Command.START_TRAJECTORY_RECORDING, {"name": self.record_name.text().strip()}
            )
        )
        for button, command in (
            (self.finish_button, Command.STOP_TRAJECTORY_RECORDING),
            (self.save_button, Command.SAVE_TRAJECTORY),
            (self.cancel_button, Command.CANCEL_TRAJECTORY_RECORDING),
            (self.refresh_button, Command.LIST_TRAJECTORIES),
        ):
            button.clicked.connect(lambda _checked=False, cmd=command: self._submit(cmd))
        self.preview_button.clicked.connect(
            lambda: self._submit(
                Command.PREVIEW_TRAJECTORY, {"trajectory_id": self.saved_combo.currentData()}
            )
        )
        self.play_button.clicked.connect(self._play)
        self.import_json_button.clicked.connect(self._import_json)
        self.import_episode_button.clicked.connect(self._import_episode)
        self.saved_combo.currentIndexChanged.connect(self._selection_changed)
        self.record_name.textChanged.connect(self._update_enabled)
        self.arm_check.toggled.connect(self._update_enabled)
        self.hand_check.toggled.connect(self._update_enabled)

    def _play(self):
        self._submit(
            Command.REPLAY_TRAJECTORY,
            {
                "trajectory_id": self.saved_combo.currentData(),
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

    def _selection_changed(self):
        selected = self.saved_combo.currentData()
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
            current = self.saved_combo.currentData()
            self._catalog = catalog
            self.saved_combo.blockSignals(True)
            self.saved_combo.clear()
            for value in catalog:
                self.saved_combo.addItem(value["name"], value["trajectory_id"])
            index = self.saved_combo.findData(current)
            self.saved_combo.setCurrentIndex(max(0, index) if catalog else -1)
            self.saved_combo.blockSignals(False)
            self._selection_changed()
        count, duration = snapshot.get("frame_count", 0), snapshot.get("duration_s", 0.0)
        state = "正在记录" if snapshot.get("recording") else "待保存" if count else "未录制"
        self.status_label.setText(
            snapshot.get("recording_error") or f"{state} · {count} 帧 · {duration:.2f}s"
        )
        self._render_preview()
        self._update_enabled()

    def _update_enabled(self):
        if self._context is None:
            return
        view, readiness, busy = self._context
        state = view.workflow_state
        recording = bool(self._snapshot.get("recording"))
        playing = bool(self._snapshot.get("playing")) or state is WorkflowState.REPLAY_RUNNING
        unsaved = (
            recording or bool(self._snapshot.get("frame_count")) or self._snapshot.get("pending")
        )
        record_allowed = view.actions.get(Command.START_TRAJECTORY_RECORDING, False)
        self.record_button.setEnabled(
            record_allowed and not busy and not unsaved and bool(self.record_name.text().strip())
        )
        self.finish_button.setEnabled(
            bool(unsaved) and not self._snapshot.get("pending") and not busy
        )
        self.save_button.setEnabled(bool(self._snapshot.get("pending")) and not busy)
        self.cancel_button.setEnabled(bool(unsaved) and not busy)
        self.record_name.setEnabled(not unsaved and not busy)
        selected = self.saved_combo.currentData() is not None
        arm, hand = self.arm_check.isChecked(), self.hand_check.isChecked()
        replay_allowed = view.actions.get(Command.REPLAY_TRAJECTORY, False)
        self.play_button.setEnabled(
            replay_allowed
            and selected
            and not busy
            and not unsaved
            and (arm or hand)
            and (not arm or any(c.isChecked() for c in self.joint_checks))
            and (not hand or readiness.o6_connected)
            and not view.episode_pending
        )
        editable = not busy and not playing
        for widget in (
            self.mode_combo,
            self.speed_spin,
            self.repeat_spin,
            self.arm_check,
            self.hand_check,
            self.saved_combo,
            self.import_json_button,
            self.import_episode_button,
            self.episode_spin,
            self.refresh_button,
        ):
            widget.setEnabled(editable)
        for check in self.joint_checks:
            check.setEnabled(editable and arm)
        self.preview_button.setEnabled(selected and editable)

    def _render_preview(self):
        preview = self._snapshot.get("preview") or {}
        if not preview or preview.get("trajectory_id") != self.saved_combo.currentData():
            text = ""
        else:

            def values(vector):
                return "无" if vector is None else ", ".join(f"{v:.4g}" for v in vector)

            def ranges(bounds):
                return "无" if bounds is None else "; ".join(f"{a:.4g}～{b:.4g}" for a, b in bounds)

            text = (
                f"{preview['name']} · {preview['robot_type']} · {preview['frame_count']} 帧 · "
                f"{preview['duration_s']:.2f}s · {preview['fps']:.1f}Hz\n"
                f"来源：{preview.get('source', '—')} · 创建：{preview.get('created_at', '—')}\n"
                f"关节范围 rad：{ranges(preview['joint_range_rad'])}\n"
                f"最大帧间变化 rad：{values(preview.get('max_joint_delta_rad'))}\n"
                f"最大关节速度 rad/s：{values(preview['max_joint_velocity_rad_s'])}\n"
                f"起点 rad：{values(preview['start_joint_rad'])}\n"
                f"终点 rad：{values(preview['end_joint_rad'])}\n"
                f"TCP 范围 m/rad：{ranges(preview['tcp_range'])}\n"
                f"Hand 范围：{ranges(preview['hand_range'])}\n"
                + "\n".join(preview.get("warnings", ()))
            )
        if self.preview_text.toPlainText() != text:
            self.preview_text.setPlainText(text)
