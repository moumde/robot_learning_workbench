"""Collection workflow presentation; no drivers, sampling, or writer ownership."""

from PySide6.QtWidgets import QMessageBox

from core.workbench.core.state_machine import Command, WorkflowState

from ..theme import set_state


def episode_label(dataset, *, active=False):
    index = dataset.get("episode_index") if active else None
    if index is None:
        index = dataset.get("next_episode_index", 0)
    return f"Episode {index:03d}"


def duration_text(seconds):
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


class CollectionController:
    """Receive the shell's single UiFrame; never poll the Presenter again."""

    def __init__(self, page, submit):
        self.page = page
        self._send = submit
        self._context = None
        self._setup_context = None
        self._was_recording = False
        self._last_receipt = None
        page.outcome_combo.currentIndexChanged.connect(self.refresh)
        page.recording_source_combo.currentIndexChanged.connect(self.refresh)
        page.task_edit.textChanged.connect(self.refresh)
        page.root_edit.textChanged.connect(self.refresh)

    def refresh(self, *_):
        if self._context is not None:
            self.render(*self._context)

    def submit(self, command, payload=None):
        page = self.page
        if command is Command.START_EPISODE:
            payload = {
                **(payload or {}),
                "source": page.recording_source_combo.currentData() or "teleop",
            }
        elif command is Command.STOP_EPISODE:
            outcome = page.outcome_combo.currentData()
            if outcome not in ("success", "failure"):
                page.episode_hint.setText("请先选择本段结果，再完成并保存。")
                return
            command, payload = Command.FINISH_EPISODE, {"outcome": outcome}
        elif command is Command.DISCARD_EPISODE:
            dataset = self._context[2] if self._context else {}
            name = episode_label(dataset, active=True)
            if (
                QMessageBox.question(
                    page,
                    "丢弃本段采集",
                    f"丢弃 {name}（{dataset.get('buffered_frames', 0)} 帧）？本段将不会作为有效 Episode 保存。",
                    QMessageBox.Yes | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                )
                != QMessageBox.Yes
            ):
                return
        self._send(command, payload)

    def render(self, view, readiness, dataset, busy=False):
        self._context = view, readiness, dataset, busy
        page = self.page
        recording, pending = view.episode_active, view.episode_pending
        if recording and not self._was_recording:
            page.outcome_combo.blockSignals(True)
            page.outcome_combo.setCurrentIndex(0)
            page.outcome_combo.blockSignals(False)
        self._was_recording = recording
        for button, command in (
            (page.connect_button, Command.CONNECT),
            (page.disconnect_button, Command.DISCONNECT),
            (page.power_on_button, Command.POWER_ON),
            (page.power_off_button, Command.POWER_OFF),
            (page.prepare_devices_button, Command.PREPARE_DEVICES),
            (page.start_teleop_button, Command.START_TELEOP),
            (page.stop_teleop_button, Command.STOP_TELEOP),
            (page.start_cameras_button, Command.START_CAMERAS),
            (page.stop_cameras_button, Command.STOP_CAMERAS),
            (page.save_success_button, Command.SAVE_SUCCESS),
            (page.save_failure_button, Command.SAVE_FAILURE),
            (page.discard_button, Command.DISCARD_EPISODE),
            (page.create_dataset_button, Command.CREATE_DATASET),
            (page.finalize_dataset_button, Command.FINALIZE_DATASET),
        ):
            allowed = view.actions.get(command, False) and not busy
            button.setEnabled(allowed)
            button.setToolTip(
                "正在处理上一项请求，请稍候。" if busy else view.action_reasons.get(command, "")
            )
        source = page.recording_source_combo.currentData() or "teleop"
        source_allowed = view.recording_sources.get(
            source, view.actions.get(Command.START_EPISODE, False)
        )
        form_ready = view.dataset_session_active or bool(
            page.task_edit.text().strip() and page.root_edit.text().strip()
        )
        page.episode_start_button.setEnabled(source_allowed and form_ready and not busy)
        page.episode_start_button.setVisible(not (recording or pending))
        page.episode_stop_button.setVisible(recording)
        page.episode_stop_button.setText("完成本段并保存")
        outcome = page.outcome_combo.currentData()
        finish_permission = view.actions.get(
            Command.SAVE_SUCCESS if outcome == "success" else Command.SAVE_FAILURE, False
        )
        page.episode_stop_button.setEnabled(
            recording and outcome in ("success", "failure") and finish_permission and not busy
        )
        page.outcome_combo.setVisible(recording)
        page.outcome_combo.setEnabled(recording and not busy)
        for button in (page.save_success_button, page.save_failure_button):
            button.setVisible(pending)
        page.discard_button.setVisible(recording or pending)
        page._role(page.discard_button, "danger")

        editable = not (
            recording
            or pending
            or busy
            or view.dataset_session_active
            or view.workflow_state is WorkflowState.DAGGER_RUNNING
        )
        for widget in (
            page.task_edit,
            page.description_edit,
            page.root_edit,
            page.root_browse_button,
        ):
            widget.setEnabled(editable)
        page.dataset_format.setEnabled(editable)
        page.dataset_format.blockSignals(True)
        page.dataset_format.setCurrentIndex(page.dataset_format.findData(view.dataset_format))
        page.dataset_format.blockSignals(False)
        page.recording_source_combo.setEnabled(not (recording or pending or busy))
        page.robot_selector.setEnabled(
            False
        )  # One installed profile; never imply a live robot switch.
        page.robot_selector.setItemText(
            0, readiness.robot_name if readiness.robot_profile else "CR3A + O6"
        )
        page.robot_selector.setToolTip(
            readiness.robot_endpoint or "当前安装的硬件配置；设备断开后在配置中选择"
        )
        page.control_source.setItemText(
            0, readiness.master_type.upper() if readiness.master_type != "unknown" else "GELLO"
        )
        page.control_source.setToolTip("当前输入源；设备未断开时不可切换")
        setup_context = bool(view.dataset_session_active or recording or pending)
        if setup_context != self._setup_context:
            self._setup_context = setup_context
            page.dataset_setup_toggle.setChecked(not setup_context)
        page.resume_dataset_button.setEnabled(
            not (recording or pending or busy or view.dataset_session_active)
        )
        self._render_preparation(view, readiness, dataset, busy)
        self._render_recording(view, readiness, dataset, busy, source, source_allowed, form_ready)
        self._render_advanced(view, readiness, busy)

    def _render_preparation(self, view, ready, dataset, busy):
        page, state = self.page, view.workflow_state
        connected = (
            ready.robot_connected
            if ready.robot_connected is not None
            else view.robot_state.name not in ("OFFLINE", "FAULT", "ESTOP")
        )
        enabled = (
            ready.servo_state == "on"
            if ready.servo_state is not None
            else view.robot_state.name == "ENABLED"
        )
        teleop = state is WorkflowState.TELEOP_RUNNING
        device_text = (
            "输入与末端已就绪"
            if ready.devices_ready
            else ready.master_error
            or ready.o6_error
            or (
                "设备已连接，等待反馈"
                if ready.master_connected
                else "串口已发现，尚未连接"
                if ready.master_discovered
                else "等待连接遥操设备"
            )
        )
        values = (
            ("机器人已连接" if connected else "机器人未连接", connected),
            (device_text, ready.devices_ready),
            ("Servo ON" if enabled else "等待明确上使能", enabled),
            (
                "遥操跟随运行中"
                if teleop
                else "就绪，尚未启用遥操"
                if enabled and ready.devices_ready
                else "等待遥操准备",
                teleop,
            ),
        )
        for label, (text, success) in zip(page.stage_status_labels, values, strict=True):
            label.setText(text)
            set_state(label, "success" if success else "neutral")
        next_button = None
        if busy:
            hint = "正在处理上一项请求，请稍候。"
        elif state in (WorkflowState.FAULT, WorkflowState.ESTOP):
            hint = "故障或软件急停已锁定；先处理本段数据，再在机器人状态页明确复位。"
        elif view.episode_pending:
            hint = "本段待处理；请选择失败/成功保存或明确丢弃。"
        elif view.episode_active:
            hint = "正在录制 · 选择结果后完成本段，或明确丢弃。"
        elif not connected:
            hint, next_button = "下一步：连接机器人；相机可独立启动。", page.connect_button
        elif not enabled:
            hint, next_button = "下一步：确认机器人状态并明确上使能。", page.power_on_button
        elif teleop:
            hint = "遥操运行中 · 确认任务、数据集和相机后开始 Recording。"
        elif view.motion_state.name in ("REPLAY", "POINT_MOVE", "HOME", "POLICY"):
            hint = "当前正在执行其他运动；回放或走点采集请明确选择对应来源，启用遥操前先停止运动。"
        elif not ready.devices_ready:
            hint, next_button = (
                "下一步：连接遥操设备，确认主臂与末端反馈就绪。",
                page.prepare_devices_button,
            )
        else:
            hint, next_button = "下一步：启用遥操，建立主从跟随。", page.start_teleop_button
        page.preparation_hint.setText(hint)
        for button in (
            page.connect_button,
            page.prepare_devices_button,
            page.power_on_button,
            page.start_teleop_button,
        ):
            page._role(
                button, "primary" if button is next_button and button.isEnabled() else "quiet"
            )
        if ready.camera_error:
            camera_hint = ready.camera_error
        elif ready.camera_frames_ready:
            camera_hint = "画面已就绪 · 预览与采集使用相同来源"
        else:
            camera_hint = (
                "相机运行中 · 等待新鲜画面" if ready.cameras_running else "相机未启动 · 可独立准备"
            )
        page.camera_hint.setText(camera_hint)
        set_state(
            page.camera_hint,
            "error"
            if ready.camera_error
            else "success"
            if ready.camera_frames_ready
            else "neutral",
        )

    def _render_recording(self, view, ready, dataset, busy, source, source_allowed, form_ready):
        page = self.page
        quality = dataset.get("quality", {})
        task = dataset.get("batch_task") or page.task_edit.text().strip() or "尚未设置任务"
        format_name = {
            "lerobot_v3": "LeRobot V3",
            "lerobot_v21": "LeRobot V2.1",
            "hdf5": "HDF5",
        }.get(view.dataset_format, view.dataset_format)
        page.session_summary.setText(f"{task} · {format_name}")
        page.session_summary.setToolTip(
            dataset.get("root") or dataset.get("output_root") or page.root_edit.text()
        )
        page.episode_id_label.setText(
            episode_label(dataset, active=view.episode_active or view.episode_pending)
        )
        page.saved_metric.setText(str(view.saved_episodes))
        page.frame_metric.setText(str(view.buffered_frames))
        page.duration_metric.setText(duration_text(dataset.get("duration", 0)))
        page.fps_metric.setText(f"{quality.get('effective_fps', 0):.1f} FPS")
        dropped = quality.get("dropped_frames")
        page.dropped_metric.setText("丢帧：未统计" if dropped is None else f"丢帧：{dropped}")
        page.dropped_metric.setToolTip(
            f"跳过采样槽 {quality.get('skipped_samples', 0)}；迟帧 {quality.get('late_frames', 0)}；相机重复 {quality.get('reused_camera_frames', {})}。这些不等同于相机丢帧。"
        )
        severity = "neutral"
        if busy:
            headline, hint = (
                view.activity_text or "请求处理中",
                "请等待当前操作完成；全局停止与 F12 仍可用。",
            )
        elif view.episode_pending:
            headline, severity = "本段未保存", "warning"
            if not view.buffered_frames:
                hint = "暂无可保存帧，请明确丢弃本段 Episode。"
            elif view.recording_error or view.workflow_state in (
                WorkflowState.FAULT,
                WorkflowState.ESTOP,
            ):
                hint = "采集故障或急停后只能保存失败 Episode 或丢弃。" + view.recording_error
            else:
                hint = "请选择成功或失败保存，或明确丢弃后继续。"
        elif view.episode_active:
            headline, severity = "● REC · 正在采集并写入批次", "success"
            hint = "选择本段结果后完成并保存；停止运动不会自动保存本段。"
        elif view.workflow_state in (WorkflowState.FAULT, WorkflowState.ESTOP):
            headline, hint, severity = (
                "故障待处理",
                "请排查设备并明确复位，复位后保持停止。",
                "error",
            )
        elif not source_allowed:
            headline, hint = (
                "等待采集准备",
                view.recording_source_reasons.get(source)
                or "请先启动所选运动来源，并确认相机就绪。",
            )
        elif not form_ready:
            headline, hint = "设置本次采集任务", "填写任务名称和保存目录，或继续未完成批次。"
        else:
            headline, hint = (
                "可以开始录制",
                "格式和任务在采集会话期间锁定；开始后按本段结果完成或丢弃。",
            )
        if view.quality_needs_review:
            hint += " 本段采集质量需复核，展开采集详情查看。"
            if severity != "error":
                severity = "warning"
        page.episode_headline.setText(headline)
        page.episode_hint.setText(hint)
        page.episode_start_button.setToolTip(hint)
        page.episode_stop_button.setToolTip("请选择明确结果，再完成本段并保存。")
        set_state(page.episode_headline, severity)
        set_state(page.episode_state_panel, severity)
        text = f"采样来源 {source} · 配置 {quality.get('configured_fps', 0):g} FPS\n跳过采样槽 {quality.get('skipped_samples', 0)} · 迟帧 {quality.get('late_frames', 0)}\n相机重复 {quality.get('reused_camera_frames', {})}\n实际保存：{dataset.get('root', '')}"
        if dataset.get("batch_id"):
            text += f"\nBatch {dataset['batch_id'][:8]} · {dataset.get('segment_id', '')}"
        if view.dataset_validation:
            report = view.dataset_validation
            text += "\nDataset validation: " + ("PASS" if report["valid"] else "FAILED")
            text += " · " + "; ".join(report.get("errors", ()))
        page.episode_status.setText(text)
        page.name_preview.setText(dataset.get("dataset_name_preview", ""))
        receipt = dataset.get("last_saved")
        if receipt and receipt != self._last_receipt:
            self._last_receipt = dict(receipt)
            outcome = "成功" if receipt.get("outcome") == "success" else "失败"
            index = receipt.get("episode_index", 0)
            page.save_receipt.setText(
                f"Episode {index:03d} 已保存（{outcome}） · {receipt.get('frame_count', 0)} 帧\n{receipt.get('root', '')}"
            )
        page.save_receipt.setVisible(bool(receipt))
        set_state(page.save_receipt, "success")
        if not view.dataset_session_active and view.dataset_validation:
            report = view.dataset_validation
            page.save_receipt.setVisible(True)
            page.save_receipt.setText(
                ("数据集已完成并发布" if report["valid"] else "数据集校验失败，尚未成功发布")
                + "\n"
                + str(dataset.get("root", ""))
            )
            set_state(page.save_receipt, "success" if report["valid"] else "error")

    def _render_advanced(self, view, ready, busy):
        page = self.page
        dagger = view.workflow_state is WorkflowState.DAGGER_RUNNING
        page.dagger_start_button.setEnabled(
            view.actions.get(Command.START_DAGGER, False)
            and ready.devices_ready
            and ready.camera_frames_ready
            and not busy
            and not (view.episode_active or view.episode_pending)
        )
        page.dagger_toggle_button.setEnabled(dagger and not busy)
        page.dagger_stop_button.setEnabled(dagger and not busy)
        page.dagger_status.setText(
            f"{view.dagger_phase or '未运行'} · {view.dagger_expert_frames} 专家帧\n{view.dagger_root}"
        )
