"""Single Workbench shell: page navigation, snapshots, and application commands."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox

from teleop.gello_cr import __version__
from teleop.gello_cr.app.background import BackgroundJobs
from teleop.gello_cr.app.datasets import preview_dataset_name
from teleop.gello_cr.core.state_machine import Command, WorkflowState

from .camera_preview import CameraPreviewRenderer
from .command_port import CommandRequest
from .emergency_shortcut import EmergencyStopFilter
from .generated.ui_main_window import Ui_OperatorMainWindow
from .motion_workspace import MotionWorkspace
from .pages.collection import CollectionPage
from .pages.dataset_manager import DatasetManagerPage
from .pages.robot_status import RobotStatusPage
from .status_presenter import render_status
from .theme import WORKBENCH_STYLESHEET, set_state


class WorkbenchPage(IntEnum):
    COLLECTION = 0
    MOTION = 1
    DATASETS = 2
    ROBOT = 3
    SETTINGS = 4


class OperatorMainWindow(QMainWindow):
    shutdown_finished = Signal(object)

    def __init__(
        self,
        presenter,
        command_port,
        *,
        refresh_ms=100,
        close_callback=None,
        settings_factory=None,
        parent=None,
    ):
        super().__init__(parent)
        self._jobs = BackgroundJobs()
        self._presenter, self._command_port = presenter, command_port
        self._close_callback, self._settings_factory = close_callback, settings_factory
        self._closing = self._shutdown_complete = self._settings_restart_required = False
        self._shown_batch = ""
        self.settings_editor = None
        self._local_error = ""
        self._ui = Ui_OperatorMainWindow()
        self._ui.setupUi(self)
        self.workflow_label = self._ui.shell_workflow_label
        self.workflow_detail = self._ui.shell_workflow_detail
        self.home_button = self._ui.shell_home_button
        self.stop_motion_button = self._ui.shell_stop_motion_button
        self.estop_button = self._ui.shell_estop_button
        self.robot_badge = self._ui.shell_robot_badge
        self.motion_badge = self._ui.shell_motion_badge
        self.recording_badge = self._ui.shell_recording_badge
        self.state_headline = self._ui.shell_state_headline
        self.navigation = self._ui.shell_navigation
        self.pages = self._ui.shell_pages
        self.settings_page = self._ui.shell_settings_page
        self.settings_layout = self._ui.shell_settings_layout
        self.settings_note = self._ui.shell_settings_note
        self.notification = self._ui.shell_notification
        self.recovery_button = self._ui.shell_recovery_button
        self.log_toggle = self._ui.shell_log_toggle
        self.event_log = self._ui.shell_event_log
        self.summary_status = self._ui.shell_summary_status
        self.brand_version = self._ui.shell_brand_version
        self.servo_badge = self._ui.shell_servo_badge
        self.master_badge = self._ui.shell_master_badge
        self.teleop_badge = self._ui.shell_teleop_badge
        self.identity_label = self._ui.shell_identity_label
        self.dataset_label = self._ui.shell_dataset_label
        self.episode_label = self._ui.shell_episode_label
        self.fps_label = self._ui.shell_fps_label
        self.setWindowTitle(f"Robot Learning Workbench v{__version__}")
        self.brand_version.setText(f"ROBOT LEARNING  /  v{__version__}")
        self.collection = CollectionPage(self._submit, self._ui.shell_collection)
        self._preview_renderer = CameraPreviewRenderer(self.collection)
        self.motion_workspace = MotionWorkspace(self._submit, self._ui.shell_motion_workspace)
        self.trajectory_panel = self.motion_workspace.trajectory_panel
        self.planning_panel = self.motion_workspace.planning_panel
        self.dataset_page = DatasetManagerPage(self._submit, self._ui.shell_dataset_page)
        self.robot_page = RobotStatusPage(self._submit, self._ui.shell_robot_page)
        for host, page in (
            (self._ui.shell_collection, self.collection),
            (self._ui.shell_motion_workspace, self.motion_workspace),
            (self._ui.shell_dataset_page, self.dataset_page),
            (self._ui.shell_robot_page, self.robot_page),
        ):
            host.layout().addWidget(page)
        self.statusBar().addPermanentWidget(self.summary_status, 1)
        self.navigation.currentRowChanged.connect(self._navigate)
        for button, command in (
            (self.home_button, Command.RETURN_HOME),
            (self.stop_motion_button, Command.STOP_MOTION),
            (self.estop_button, Command.EMERGENCY_STOP),
        ):
            button.clicked.connect(lambda checked=False, cmd=command: self._submit(cmd))
        self.recovery_button.clicked.connect(
            lambda: self.navigation.setCurrentRow(WorkbenchPage.DATASETS)
        )
        self.collection.manage_datasets.connect(
            lambda: self.navigation.setCurrentRow(WorkbenchPage.DATASETS)
        )
        self.robot_page.connection_requested.connect(
            lambda: self.navigation.setCurrentRow(WorkbenchPage.COLLECTION)
        )
        self.log_toggle.toggled.connect(self.event_log.setVisible)
        self.log_toggle.toggled.connect(
            lambda expanded: self.log_toggle.setText("运行日志  ▴" if expanded else "运行日志  ▾")
        )
        self.event_log.document().setMaximumBlockCount(400)
        self.setStyleSheet(WORKBENCH_STYLESHEET)
        self._emergency_filter = EmergencyStopFilter(
            self, lambda: self._submit(Command.EMERGENCY_STOP)
        )
        self._dagger_shortcut = QShortcut(QKeySequence("Space"), self)
        self._dagger_shortcut.setAutoRepeat(False)
        self._dagger_shortcut.activated.connect(lambda: self._submit(Command.TOGGLE_INTERVENTION))
        self.shutdown_finished.connect(self._finish_shutdown)
        self._timer = QTimer(self)
        self._timer.setInterval(max(50, int(refresh_ms)))
        self._timer.timeout.connect(self.refresh_from_presenter)
        self.navigation.setCurrentRow(0)
        self._timer.start()
        self.refresh_from_presenter()

    def _navigate(self, index):
        self.pages.setCurrentIndex(index)
        if 0 <= index < self.navigation.count():
            self.workflow_label.setText(self.navigation.item(index).text())
            self.workflow_detail.setText(
                (
                    "准备设备，观察画面，记录每一次有效操作",
                    "录制示教、预览回放、规划走点，共用同一个轨迹库",
                    "浏览数据集，校验质量，处理未完成批次",
                    "查看设备反馈与故障，明确复位后保持停止",
                    "设备连接、运动与采集参数",
                )[index]
            )
        if index == WorkbenchPage.SETTINGS and self.settings_editor is None:
            self._open_settings()
            self.refresh_from_presenter()

    def _open_settings(self):
        if self._settings_factory is None:
            self.settings_note.setText("此启动方式未配置设置存储；其余离线页面可正常使用。")
            return
        from .settings_dialog import OperatorSettingsDialog

        try:
            editor = OperatorSettingsDialog(self._settings_factory(), self, embedded=True)
        except (ValueError, OSError, RuntimeError) as exc:
            self._local_error = f"无法读取设置：{exc}"
            self.notification.setText(self._local_error)
            return
        self.settings_editor = editor
        self.settings_layout.insertWidget(1, editor, 1)
        editor.saved_changes.connect(self._settings_saved)
        editor.reload_requested.connect(self._reload_settings)

    def _reload_settings(self):
        old = self.settings_editor
        if old:
            try:
                old.close_jobs(timeout=0)
            except TimeoutError:
                self.notification.setText("相机发现仍在执行，请完成后再重新加载设置。")
                return
            self.settings_editor = None
            self.settings_layout.removeWidget(old)
            old.deleteLater()
        self._open_settings()

    def _settings_saved(self):
        self._settings_restart_required = True
        self.notification.setText("参数已保存，请重新启动后连接设备。")
        self.refresh_from_presenter()

    def _submit(self, command, payload=None):
        if (
            command is Command.RESET_ESTOP
            and QMessageBox.question(
                self,
                "解除软件急停",
                "确认现场允许解除软件急停？复位后保持停止。",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            != QMessageBox.Yes
        ):
            return
        try:
            self._command_port.submit(CommandRequest.create(command, payload))
            self._local_error = ""
        except Exception as exc:
            self._local_error = f"{command.name}: {exc}"
            self.notification.setText(self._local_error)
            self.event_log.appendPlainText(f"ERROR · {command.name}: {exc}")
        self.refresh_from_presenter()

    def refresh_from_presenter(self):
        if self._presenter.closed:
            self._timer.stop()
            return
        frame = self._presenter.poll()
        view, readiness = frame.view_model, frame.readiness
        pending = getattr(self._command_port, "pending_commands", frozenset())
        busy = bool(pending)
        dataset = dict(frame.dataset)
        dataset["dataset_name_preview"] = preview_dataset_name(
            self.collection.task_edit.text(), view.dataset_format
        )
        self.collection.render(view, readiness, dataset, busy)
        self.motion_workspace.render(frame.trajectory, frame.planning, view, readiness, busy)
        self.dataset_page.render(frame.catalog, dataset, busy)
        if not self.dataset_page.root_edit.text():
            self.dataset_page.root_edit.setText(self.collection.root_edit.text())
        self.robot_page.render(view, readiness, frame.diagnostics, busy)
        self._dagger_shortcut.setEnabled(
            view.workflow_state is WorkflowState.DAGGER_RUNNING and not busy and not self._closing
        )
        self.home_button.setVisible(
            not readiness.robot_profile or readiness.capabilities.supports_home
        )
        self.home_button.setToolTip(
            view.action_reasons.get(Command.RETURN_HOME) or "返回已标定的 HOME，到位后保持停止"
        )
        self.home_button.setEnabled(
            view.actions[Command.RETURN_HOME]
            and not pending.intersection(
                {
                    Command.RETURN_HOME,
                    Command.HOME_AND_SAVE_EPISODE,
                    Command.STOP_MOTION,
                    Command.EMERGENCY_STOP,
                    Command.REPORT_FAULT,
                }
            )
        )
        self.collection.return_home_button.setEnabled(self.home_button.isEnabled())
        self.stop_motion_button.setEnabled(view.actions[Command.STOP_MOTION])
        self.estop_button.setEnabled(view.actions[Command.EMERGENCY_STOP])
        render_status(self, frame, pending, self._local_error)
        settings_allowed = view.settings_editable and not busy
        if self.settings_editor:
            self.settings_editor.setEnabled(settings_allowed)
        if self._settings_restart_required:
            self.state_headline.setText("参数已保存 · 请关闭并重新启动程序后连接设备")
            set_state(self.state_headline, "warning")
            self.collection.connect_button.setEnabled(False)
            self.collection.start_cameras_button.setEnabled(False)
        batch_id = dataset.get("batch_id", "")
        if batch_id and batch_id != self._shown_batch:
            self.collection.task_edit.setText(dataset.get("batch_task", ""))
            self.collection.description_edit.setText(dataset.get("task_description", ""))
            self.collection.root_edit.setText(dataset.get("output_root", ""))
        self._shown_batch = batch_id
        recoverable = dataset.get("recoverable_batches", ())
        self.recovery_button.setVisible(bool(recoverable))
        self.recovery_button.setText(f"{len(recoverable)} 个未完成批次 · 查看")
        self.render_preview(frame.preview)
        for event in frame.events:
            stamp = datetime.fromtimestamp(event.occurred_at).strftime("%H:%M:%S")
            self.event_log.appendPlainText(f"{stamp} {event.level.value.upper()} · {event.message}")

    def render_preview(self, preview):
        self._preview_renderer.render(preview)

    def closeEvent(self, event):
        if self._shutdown_complete:
            self._timer.stop()
            self._emergency_filter.detach()
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        save_pending = False
        if not self._presenter.closed:
            frame = self._presenter.poll()
            view = frame.view_model
            if frame.dataset.get("partial_episodes"):
                self.notification.setText("请先在数据集管理处理 Partial，或保留当前批次稍后继续。")
                self.navigation.setCurrentRow(WorkbenchPage.DATASETS)
                return
            trajectory = frame.trajectory
            save_pending = (
                view.episode_active
                or view.episode_pending
                or bool(
                    trajectory.get("recording")
                    or trajectory.get("pending")
                    or trajectory.get("frame_count")
                )
            )
            if (
                save_pending
                and QMessageBox.question(
                    self,
                    "保存数据并退出",
                    "停止运动，保存未完成轨迹及 Episode（Episode 标为失败）后退出？",
                    QMessageBox.Yes | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                )
                != QMessageBox.Yes
            ):
                return
        self._closing = True
        self._timer.stop()
        self._dagger_shortcut.setEnabled(False)
        self.notification.setText("正在停止运动、保存数据并释放设备…")
        self.notification.show()

        def close():
            errors = []
            try:
                if self._close_callback is not None:
                    self._close_callback(**({"save_pending": True} if save_pending else {}))
                else:
                    self._command_port.close(timeout=1)
                    self._presenter.close()
            except Exception as exc:
                errors.append(exc)
            try:
                if self.settings_editor is not None:
                    self.settings_editor.close_jobs()
            except Exception as exc:
                errors.append(exc)
            if errors:
                raise ExceptionGroup("Workbench shutdown incomplete", errors)

        self._jobs.start(
            close,
            lambda value, error: self.shutdown_finished.emit(error),
            name="Workbench-Shutdown",
        )

    def _finish_shutdown(self, error):
        self._closing = False
        if error:
            self._local_error = f"退出未完成：{error}；可再次关闭重试。"
            self.notification.setText(self._local_error)
            if not self._presenter.closed:
                self._timer.start()
            return
        self._shutdown_complete = True
        self.close()
