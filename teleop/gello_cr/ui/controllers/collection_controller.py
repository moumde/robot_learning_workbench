"""Collection workflow presentation; no drivers, sampling, or writer ownership."""

from PySide6.QtWidgets import QMessageBox

from teleop.gello_cr.core.state_machine import Command, WorkflowState

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
        self._last_receipt = None
        page.recording_source_combo.currentIndexChanged.connect(self.refresh)
        page.task_edit.textChanged.connect(self.refresh)
        page.root_edit.textChanged.connect(self.refresh)

    def refresh(self, *_):
        if self._context is not None:
            self.render(*self._context)

    def submit(self, command, payload=None):
        page = self.page
        if command is Command.START_EPISODE:
            source = page.recording_source_combo.currentData() or "teleop"
            if source == "teleop":
                view = self._context[0] if self._context else None
                if (
                    view
                    and view.episode_active
                    and view.workflow_state is WorkflowState.ROBOT_ENABLED
                ):
                    command, payload = Command.START_TELEOP, None
                else:
                    command, payload = (
                        Command.START_COLLECTION,
                        {**(payload or {}), "source": source},
                    )
            else:
                payload = {**(payload or {}), "source": source}
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
        resume_teleop = (
            recording and source == "teleop" and view.workflow_state is WorkflowState.ROBOT_ENABLED
        )
        start_allowed = (
            view.actions.get(Command.START_TELEOP, False)
            if resume_teleop
            else source_allowed and form_ready and not (recording or pending)
        )
        page.episode_start_button.setText("重新开始遥操" if resume_teleop else "开始采集")
        page.episode_start_button.setVisible(True)
        page.episode_start_button.setEnabled(start_allowed and not busy)
        supports_home = not readiness.robot_profile or readiness.capabilities.supports_home
        page.return_home_button.setVisible(supports_home)
        page.return_home_button.setEnabled(view.actions.get(Command.RETURN_HOME, False))
        home_reason = view.action_reasons.get(Command.RETURN_HOME, "")
        page.return_home_button.setToolTip(home_reason or "返回 HOME；当前 Episode 继续录制")
        page.episode_stop_button.setVisible(supports_home)
        page.episode_stop_button.setEnabled(
            recording and view.actions.get(Command.HOME_AND_SAVE_EPISODE, False) and not busy
        )
        page.episode_stop_button.setToolTip(
            "正在处理上一项请求，请稍候。"
            if busy
            else view.action_reasons.get(Command.HOME_AND_SAVE_EPISODE)
            or "回到 HOME，确认到位后成功保存本段。"
        )
        for button in (page.save_success_button, page.save_failure_button, page.discard_button):
            button.setVisible(True)
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
            hint = "回 HOME 并成功保存，或直接选择成功保存、失败保存；独立回 HOME 后继续录制。"
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
                "可以开始采集",
                "开始采集后，回 HOME 并成功保存，或直接选择成功保存、失败保存。",
            )
        if view.quality_needs_review:
            hint += " 本段采集质量需复核，展开采集详情查看。"
            if severity != "error":
                severity = "warning"
        page.episode_headline.setText(headline)
        page.episode_hint.setText(hint)
        if page.episode_start_button.isEnabled():
            start_hint = (
                "继续当前 Episode 的遥操，不新建 Episode"
                if view.episode_active
                else "启动遥操并开始录制"
                if source == "teleop"
                else "录制所选运动来源"
            )
        else:
            start_hint = hint
        page.episode_start_button.setToolTip(start_hint)
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
