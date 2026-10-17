"""Collection page: device intents, logical camera streams, Dataset and Episode controls."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QWidget

from gello_cr.core.state_machine import Command

from ..controllers.collection_controller import CollectionController
from ..generated.ui_collection_page import Ui_CollectionPage


class CollectionPage(QWidget):
    manage_datasets = Signal()

    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self._submit = submit
        self._ui = Ui_CollectionPage()
        self._ui.setupUi(self)
        self.preparation_hint = self._ui.collection_preparation_hint
        self.connect_button = self._ui.collection_connect_button
        self.prepare_devices_button = self._ui.collection_prepare_devices_button
        self.power_on_button = self._ui.collection_power_on_button
        self.start_teleop_button = self._ui.collection_start_teleop_button
        self.disconnect_button = self._ui.collection_disconnect_button
        self.power_off_button = self._ui.collection_power_off_button
        self.stop_teleop_button = self._ui.collection_stop_teleop_button
        self.start_cameras_button = self._ui.collection_start_cameras_button
        self.stop_cameras_button = self._ui.collection_stop_cameras_button
        self.stage_status_labels = [
            self._ui.collection_stage_status_labels_0,
            self._ui.collection_stage_status_labels_1,
            self._ui.collection_stage_status_labels_2,
            self._ui.collection_stage_status_labels_3,
        ]
        self.workspace_splitter = self._ui.collection_workspace_splitter
        self.control_source = self._ui.collection_control_source
        self.camera_hint = self._ui.collection_camera_hint
        self.base_preview = self._ui.collection_base_preview
        self.wrist_preview = self._ui.collection_wrist_preview
        self.roi_preview = self._ui.collection_roi_preview
        self.preview_titles = [
            self._ui.collection_preview_titles_0,
            self._ui.collection_preview_titles_1,
            self._ui.collection_preview_titles_2,
        ]
        self.camera_metrics = [
            self._ui.collection_camera_metrics_0,
            self._ui.collection_camera_metrics_1,
            self._ui.collection_camera_metrics_2,
        ]
        self._session_layout = self._ui.collection_session_layout
        self.session_summary = self._ui.collection_session_summary
        self.task_edit = self._ui.collection_task_edit
        self.description_edit = self._ui.collection_description_edit
        self.dataset_setup = self._ui.collection_dataset_setup
        self.dataset_format = self._ui.collection_dataset_format
        self.create_dataset_button = self._ui.collection_create_dataset_button
        self.finalize_dataset_button = self._ui.collection_finalize_dataset_button
        self.root_edit = self._ui.collection_root_edit
        self.root_browse_button = self._ui.collection_root_browse_button
        self.name_preview = self._ui.collection_name_preview
        self.episode_state_panel = self._ui.collection_episode_state_panel
        self.episode_headline = self._ui.collection_episode_headline
        self.episode_hint = self._ui.collection_episode_hint
        self.saved_metric = self._ui.collection_saved_metric
        self.frame_metric = self._ui.collection_frame_metric
        self.duration_metric = self._ui.collection_duration_metric
        self.episode_start_button = self._ui.collection_episode_start_button
        self.episode_stop_button = self._ui.collection_episode_stop_button
        self.save_success_button = self._ui.collection_save_success_button
        self.save_failure_button = self._ui.collection_save_failure_button
        self.discard_button = self._ui.collection_discard_button
        self.episode_status = self._ui.collection_episode_status
        self.episode_details_toggle = self._ui.collection_episode_details_toggle
        self.dataset_setup_toggle = self._ui.collection_dataset_setup_toggle
        self.dagger_expander = self._ui.collection_dagger_expander
        self.dagger_host = self._ui.collection_dagger_host
        self.dagger_port = self._ui.collection_dagger_port
        self.dagger_round = self._ui.collection_dagger_round
        self.dagger_start_button = self._ui.collection_dagger_start_button
        self.dagger_toggle_button = self._ui.collection_dagger_toggle_button
        self.dagger_stop_button = self._ui.collection_dagger_stop_button
        self.dagger_root = self._ui.collection_dagger_root
        self.dagger_status = self._ui.collection_dagger_status
        self.dagger_panel = self._ui.collection_dagger_panel
        self.dagger_content = self._ui.collection_dagger_content
        self.robot_selector = self._ui.collection_robot_selector
        self.episode_id_label = self._ui.collection_episode_id_label
        self.outcome_combo = self._ui.collection_outcome_combo
        self.save_receipt = self._ui.collection_save_receipt
        self.fps_metric = self._ui.collection_fps_metric
        self.dropped_metric = self._ui.collection_dropped_metric
        self.recording_source_combo = self._ui.collection_recording_source_combo
        self.resume_dataset_button = self._ui.collection_resume_dataset_button
        self._ui.collection_robot_selector.setItemData(0, "cr3a_o6")
        self._ui.collection_control_source.setItemData(0, "gello")
        self._ui.collection_outcome_combo.setItemData(1, "success")
        self._ui.collection_outcome_combo.setItemData(2, "failure")
        self._ui.collection_recording_source_combo.setItemData(0, "teleop")
        self._ui.collection_recording_source_combo.setItemData(1, "replay")
        self._ui.collection_recording_source_combo.setItemData(2, "point_move")
        self._ui.collection_dataset_format.setItemData(0, "lerobot_v3")
        self._ui.collection_dataset_format.setItemData(1, "lerobot_v21")
        self._ui.collection_dataset_format.setItemData(2, "hdf5")
        self.controller = CollectionController(self, submit)
        self._submit = self.controller.submit
        self.resume_dataset_button.clicked.connect(self.manage_datasets)
        self.dagger_root.setText(str(Path.home() / "datasets" / "cr3_o6_dagger_raw"))
        self.workspace_splitter.setStretchFactor(0, 3)
        self.workspace_splitter.setStretchFactor(1, 2)
        self.workspace_splitter.setSizes([620, 390])
        for button, command in (
            (self.connect_button, Command.CONNECT),
            (self.prepare_devices_button, Command.PREPARE_DEVICES),
            (self.power_on_button, Command.POWER_ON),
            (self.start_teleop_button, Command.START_TELEOP),
            (self.disconnect_button, Command.DISCONNECT),
            (self.power_off_button, Command.POWER_OFF),
            (self.stop_teleop_button, Command.STOP_TELEOP),
            (self.start_cameras_button, Command.START_CAMERAS),
            (self.stop_cameras_button, Command.STOP_CAMERAS),
            (self.finalize_dataset_button, Command.FINALIZE_DATASET),
            (self.episode_stop_button, Command.STOP_EPISODE),
            (self.save_success_button, Command.SAVE_SUCCESS),
            (self.save_failure_button, Command.SAVE_FAILURE),
            (self.discard_button, Command.DISCARD_EPISODE),
            (self.dagger_toggle_button, Command.TOGGLE_INTERVENTION),
            (self.dagger_stop_button, Command.STOP_DAGGER),
        ):
            button.clicked.connect(lambda _checked=False, cmd=command: self._submit(cmd))
        self.dataset_format.currentIndexChanged.connect(
            lambda _: self._submit(
                Command.SELECT_DATASET_FORMAT, {"format": self.dataset_format.currentData()}
            )
        )
        self.create_dataset_button.clicked.connect(
            lambda: self._submit(
                Command.CREATE_DATASET,
                {
                    "task": self.task_edit.text().strip(),
                    "description": self.description_edit.text().strip(),
                    "base_root": self.root_edit.text().strip(),
                },
            )
        )
        self.root_browse_button.clicked.connect(self._choose_dataset_root)
        self.episode_start_button.clicked.connect(self._start_episode)
        self.dagger_start_button.clicked.connect(self._start_dagger)
        self.episode_details_toggle.toggled.connect(self.episode_status.setVisible)
        self.dataset_setup_toggle.toggled.connect(self._show_dataset_setup)
        self.dagger_expander.toggled.connect(self._show_dagger)

    def _show_dataset_setup(self, visible):
        self.dataset_setup.setVisible(visible)
        self.dataset_setup_toggle.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)

    def _show_dagger(self, visible):
        self.dagger_panel.setVisible(visible)
        self.dagger_content.setVisible(visible)
        self.dagger_expander.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)

    @staticmethod
    def _role(widget, role):
        if widget.property("role") != role:
            widget.setProperty("role", role)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    @staticmethod
    def _state(widget, state):
        if widget.property("state") != state:
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _start_dagger(self) -> None:
        self._submit(
            Command.START_DAGGER,
            {
                "host": self.dagger_host.text().strip(),
                "port": self.dagger_port.value(),
                "task": self.task_edit.text().strip(),
                "round_id": self.dagger_round.text().strip(),
                "base_root": self.dagger_root.text().strip(),
            },
        )

    def _choose_dataset_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择数据集父目录",
            self.root_edit.text(),
            options=QFileDialog.DontUseNativeDialog,
        )
        if path:
            self.root_edit.setText(path)
            self.root_edit.editingFinished.emit()

    def _start_episode(self) -> None:
        self._submit(
            Command.START_EPISODE,
            {
                "task": self.task_edit.text().strip(),
                "description": self.description_edit.text().strip(),
                "base_root": self.root_edit.text().strip(),
            },
        )

    def render(self, view, readiness, dataset, busy=False):
        self.controller.render(view, readiness, dataset, busy)
