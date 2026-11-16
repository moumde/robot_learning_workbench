"""Offline parameter editor with explicit camera discovery; no motion commands."""

from __future__ import annotations

import copy
import traceback

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidgetItem,
    QWidget,
)

from teleop.gello_cr.app.background import BackgroundJobs
from teleop.gello_cr.app.settings import (
    SETTINGS_GROUPS,
    OperatorSettings,
    camera_streams,
    discover_cameras,
)

from .generated.ui_settings_page import Ui_OperatorSettingsDialog
from .theme import WORKBENCH_STYLESHEET


class OperatorSettingsDialog(QDialog):
    cameras_discovered = Signal(object, str)
    saved_changes = Signal()
    reload_requested = Signal()

    def __init__(self, settings: OperatorSettings, parent=None, *, embedded=False):
        super().__init__(parent)
        self._jobs = BackgroundJobs()
        self.embedded = embedded
        if embedded:
            self.setWindowFlags(Qt.Widget)
        self.settings = settings
        self.saved = False
        self._ui = Ui_OperatorSettingsDialog()
        self._ui.setupUi(self)
        if not embedded:
            self.setStyleSheet(WORKBENCH_STYLESHEET)
        self.tabs = self._ui.settings_tabs
        self.actions_table = self._ui.settings_actions_table
        self.add_action_button = self._ui.settings_add_action_button
        self.delete_action_button = self._ui.settings_delete_action_button
        self.open_action = self._ui.settings_open_action
        self.closed_action = self._ui.settings_closed_action
        self.recording_mode = self._ui.settings_recording_mode
        self.dataset_format = self._ui.settings_dataset_format
        self.camera_scan_button = self._ui.settings_camera_scan_button
        self.camera_scan_status = self._ui.settings_camera_scan_status
        self.error_label = self._ui.settings_error_label
        self.buttons = self._ui.settings_buttons
        self.title_label = self._ui.settings_title_label
        self.profile_label = self._ui.settings_profile_label
        self.path_label = self._ui.settings_path_label
        self.fields_0 = self._ui.settings_fields_0
        self.fields_1 = self._ui.settings_fields_1
        self.master_label = self._ui.settings_master_label
        self.fields_2 = self._ui.settings_fields_2
        self.fields_3 = self._ui.settings_fields_3
        self.fields_4 = self._ui.settings_fields_4
        self.fields_5 = self._ui.settings_fields_5
        self.camera_groups = [
            self._ui.settings_camera_groups_0,
            self._ui.settings_camera_groups_1,
            self._ui.settings_camera_groups_2,
        ]
        self.camera_0_name = self._ui.settings_camera_0_name
        self.camera_0_serial = self._ui.settings_camera_0_serial
        self.camera_0_mode = self._ui.settings_camera_0_mode
        self.camera_0_roi_0 = self._ui.settings_camera_0_roi_0
        self.camera_0_roi_1 = self._ui.settings_camera_0_roi_1
        self.camera_0_roi_2 = self._ui.settings_camera_0_roi_2
        self.camera_0_roi_3 = self._ui.settings_camera_0_roi_3
        self.camera_1_name = self._ui.settings_camera_1_name
        self.camera_1_serial = self._ui.settings_camera_1_serial
        self.camera_1_mode = self._ui.settings_camera_1_mode
        self.camera_1_roi_0 = self._ui.settings_camera_1_roi_0
        self.camera_1_roi_1 = self._ui.settings_camera_1_roi_1
        self.camera_1_roi_2 = self._ui.settings_camera_1_roi_2
        self.camera_1_roi_3 = self._ui.settings_camera_1_roi_3
        self.camera_2_name = self._ui.settings_camera_2_name
        self.camera_2_serial = self._ui.settings_camera_2_serial
        self.camera_2_mode = self._ui.settings_camera_2_mode
        self.camera_2_roi_0 = self._ui.settings_camera_2_roi_0
        self.camera_2_roi_1 = self._ui.settings_camera_2_roi_1
        self.camera_2_roi_2 = self._ui.settings_camera_2_roi_2
        self.camera_2_roi_3 = self._ui.settings_camera_2_roi_3
        self._ui.settings_recording_mode.setItemData(0, "tcp")
        self._ui.settings_recording_mode.setItemData(1, "joint")
        self._ui.settings_dataset_format.setItemData(0, "lerobot_v3")
        self._ui.settings_dataset_format.setItemData(1, "lerobot_v21")
        self._ui.settings_dataset_format.setItemData(2, "hdf5")
        self._ui.settings_camera_0_mode.setItemData(0, "camera")
        self._ui.settings_camera_0_mode.setItemData(1, "roi")
        self._ui.settings_camera_1_mode.setItemData(0, "camera")
        self._ui.settings_camera_1_mode.setItemData(1, "roi")
        self._ui.settings_camera_2_mode.setItemData(0, "camera")
        self._ui.settings_camera_2_mode.setItemData(1, "roi")
        if embedded:
            self.setMinimumSize(0, 0)
        self.profile_label.setText(
            "Hardware Profile: " + settings.data["hardware"]["name"] + "（配置文件，只读）"
        )
        if settings.hardware_profile_path is not None:
            self.profile_label.setToolTip(str(settings.hardware_profile_path))
        self.path_label.setText(str(settings.path))
        self.master_label.setText(
            f"主设备：{settings.data['master']['type']}  ·  "
            f"控制模式：{settings.data.get(settings.data['master']['type'], {}).get('control_mode', '默认')}"
        )
        self.recording_mode.setCurrentIndex(
            self.recording_mode.findData(settings.data["dataset"]["recording_mode"])
        )
        self.dataset_format.setCurrentIndex(
            self.dataset_format.findData(settings.data["dataset"]["format"])
        )
        self.editors: dict[str, list[QLineEdit]] = {}
        forms = (
            self.fields_0,
            self.fields_1,
            self.fields_2,
            self.fields_3,
            self.fields_4,
            self.fields_5,
        )
        for form, fields in zip(forms, SETTINGS_GROUPS.values(), strict=True):
            # Designer owns each tab and form. The settings schema supplies the
            # variable-length scalar/vector rows and action-table cells only.
            for field in fields:
                value = field.value(settings.data)
                values = value if field.count > 1 else [value]
                row = QWidget()
                row.setObjectName(f"settings_{field.path}_row")
                row_layout = QHBoxLayout(row)
                row_layout.setObjectName(f"settings_{field.path}_row_layout")
                row_layout.setContentsMargins(0, 0, 0, 0)
                edits = []
                for index, item in enumerate(values):
                    edit = QLineEdit(str(item))
                    edit.setObjectName(f"settings_{field.path}.{index}")
                    edit.setAccessibleName(f"{field.label} {index + 1}")
                    edit.setToolTip(field.path)
                    self._apply_read_only(
                        edit, field.path if field.count == 1 else f"{field.path}.{index}"
                    )
                    edit.setMinimumWidth(45)
                    row_layout.addWidget(edit)
                    edits.append(edit)
                self.editors[field.path] = edits
                form.addRow(field.label, row)
                form.labelForField(row).setObjectName(f"settings_{field.path}_label")
        self._populate_actions()
        self._populate_camera_editors()
        # QDialogButtonBox owns its standard buttons; Designer declares the
        # button set, and we name/localize the native children after setupUi.
        for kind, name, text in (
            (QDialogButtonBox.Save, "settings_save_button", "保存参数"),
            (QDialogButtonBox.Cancel, "settings_cancel_button", "取消"),
        ):
            button = self.buttons.button(kind)
            button.setObjectName(name)
            button.setText(text)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self._initial_candidate = self._candidate()

    def _apply_read_only(self, widget, path):
        if not self.settings.is_read_only(path):
            return
        if isinstance(widget, QLineEdit):
            widget.setReadOnly(True)
        else:
            widget.setEnabled(False)
        widget.setToolTip(self.settings.read_only_reason(path))

    def _populate_camera_editors(self):
        self.camera_scan_button.clicked.connect(self._scan_cameras)
        self.camera_editors = []
        for index, stream in enumerate(camera_streams(self.settings.data["dataset"])):
            name = getattr(self, f"camera_{index}_name")
            serial = getattr(self, f"camera_{index}_serial")
            mode = getattr(self, f"camera_{index}_mode")
            roi_edits = [getattr(self, f"camera_{index}_roi_{j}") for j in range(4)]
            name.setText(stream.name)
            serial.addItem(stream.serial)
            mode.setCurrentIndex(mode.findData(stream.mode))
            for edit, value in zip(roi_edits, stream.roi_norm, strict=True):
                edit.setText(str(value))
            roi_row = roi_edits[0].parentWidget()
            roi_row.setEnabled(stream.mode == "roi")
            mode.currentIndexChanged.connect(
                lambda _index, row=roi_row, combo=mode: row.setEnabled(combo.currentData() == "roi")
            )
            path = f"dataset.camera_streams.{index}"
            for widget, key in ((name, "name"), (serial, "serial"), (mode, "mode")):
                self._apply_read_only(widget, f"{path}.{key}")
            for roi_index, edit in enumerate(roi_edits):
                self._apply_read_only(edit, f"{path}.roi_norm.{roi_index}")
            self.camera_editors.append((name, serial, mode, roi_edits))
        self.cameras_discovered.connect(self._show_cameras)

    def _scan_cameras(self):
        self.camera_scan_button.setEnabled(False)
        self.camera_scan_status.setText("正在读取相机列表…")

        discover_cameras(
            self._jobs,
            lambda value, error: self.cameras_discovered.emit(
                value or [], str(error) if error else ""
            ),
        )

    def _show_cameras(self, devices, error):
        self.camera_scan_button.setEnabled(True)
        if error:
            self.camera_scan_status.setText(f"读取相机失败：{error}")
            return
        for _name, combo, _mode, _roi in self.camera_editors:
            selected = combo.currentText().split(" · ", 1)[0].strip()
            combo.clear()
            for device in devices:
                combo.addItem(f"{device['serial']} · {device['name']}", device["serial"])
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(selected)
        self.camera_scan_status.setText(f"检测到 {len(devices)} 台相机；刷新不会更改已选序列号。")

    def _populate_actions(self):
        self.actions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.actions_table.verticalHeader().setVisible(False)
        for name, values in self.settings.data["o6"]["actions"].items():
            self._add_action(name, values)
        self.actions_table.itemChanged.connect(self._refresh_action_choices)
        self.add_action_button.clicked.connect(self._new_action)
        self.delete_action_button.clicked.connect(self._delete_action)
        self._refresh_action_choices()
        self.open_action.setCurrentText(self.settings.data["o6"]["open_action"])
        self.closed_action.setCurrentText(self.settings.data["o6"]["closed_action"])

    def _add_action(self, name, values):
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        self.actions_table.setItem(row, 0, QTableWidgetItem(name))
        for column, value in enumerate(values, 1):
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setValue(value)
            self.actions_table.setCellWidget(row, column, spin)

    def _new_action(self):
        names = {
            self.actions_table.item(row, 0).text() for row in range(self.actions_table.rowCount())
        }
        index = 1
        while f"新动作 {index}" in names:
            index += 1
        # Start from the selected saved pose, never an invented hardware target.
        values = self.settings.data["o6"]["actions"]["张开手"]
        selected = self.actions_table.currentRow()
        if selected >= 0:
            values = [self.actions_table.cellWidget(selected, c).value() for c in range(1, 7)]
        self._add_action(f"新动作 {index}", values)
        self._refresh_action_choices()
        self.actions_table.selectRow(self.actions_table.rowCount() - 1)

    def _delete_action(self):
        row = self.actions_table.currentRow()
        if row < 0:
            self.error_label.setText("请先选择要删除的动作。")
            return
        name = self.actions_table.item(row, 0).text().strip()
        if name in (
            "张开手",
            "抓取",
            self.open_action.currentText(),
            self.closed_action.currentText(),
        ):
            self.error_label.setText("张开手、抓取与已选开合动作需要保留；请先切换开合选择。")
            return
        self.actions_table.removeRow(row)
        self._refresh_action_choices()

    def _refresh_action_choices(self):
        names = [
            self.actions_table.item(row, 0).text().strip()
            for row in range(self.actions_table.rowCount())
        ]
        for combo in (self.open_action, self.closed_action):
            current = combo.currentText()
            combo.clear()
            combo.addItems(names)
            combo.setCurrentIndex(combo.findText(current))

    def _candidate(self):
        candidate = copy.deepcopy(self.settings.data)
        for fields in SETTINGS_GROUPS.values():
            for field in fields:
                field.assign(
                    candidate, field.parse([edit.text() for edit in self.editors[field.path]])
                )
        candidate["dataset"]["format"] = self.dataset_format.currentData()
        candidate["dataset"]["recording_mode"] = self.recording_mode.currentData()
        streams = [
            {
                "name": name.text().strip(),
                "serial": serial.currentText().split(" · ", 1)[0].strip(),
                "mode": mode.currentData(),
                "roi_norm": [float(edit.text()) for edit in roi_edits],
            }
            for name, serial, mode, roi_edits in self.camera_editors
        ]
        # Preserve an untouched legacy config; persist explicit slots on the first edit.
        original = camera_streams(self.settings.data["dataset"])
        parsed = camera_streams({"camera_streams": streams})
        if self.settings.data["dataset"].get("camera_streams") is not None or any(
            (a.name, a.serial, a.mode, tuple(a.roi_norm))
            != (b.name, b.serial, b.mode, tuple(b.roi_norm))
            for a, b in zip(original, parsed, strict=True)
        ):
            candidate["dataset"]["camera_streams"] = streams
        actions = {}
        for row in range(self.actions_table.rowCount()):
            name = self.actions_table.item(row, 0).text().strip()
            if not name or name in actions:
                raise ValueError("O6 动作名称不能为空或重复")
            actions[name] = [self.actions_table.cellWidget(row, c).value() for c in range(1, 7)]
        if not {"张开手", "抓取"} <= actions.keys():
            raise ValueError("请保留内置动作名称“张开手”和“抓取”，可修改其目标值")
        o6 = candidate["o6"]
        o6["actions"] = actions
        for key, combo, endpoint in (
            ("open_action", self.open_action, "open"),
            ("closed_action", self.closed_action, "closed"),
        ):
            name = combo.currentText()
            if name not in actions:
                raise ValueError("请选择有效的 J7 张开 / 闭合动作")
            o6[key] = name
            previous = self.settings.data["o6"]
            if name != previous[key] or actions[name] != previous["actions"][name]:
                o6[endpoint] = actions[name].copy()
        return candidate

    def _save(self):
        try:
            self.settings.save(self._candidate())
        except (ValueError, OSError, RuntimeError) as exc:
            traceback.print_exception(exc)
            self.error_label.setText(f"保存失败：{exc}")
            return
        self.saved = True
        self.saved_changes.emit()
        if not self.embedded:
            self.accept()
        else:
            self.error_label.setText("参数已保存；请重新启动后连接设备。")

    def reject(self):
        try:
            dirty = self._candidate() != self._initial_candidate
        except ValueError:
            dirty = True
        if (
            dirty
            and QMessageBox.question(
                self,
                "放弃未保存修改",
                "参数尚未保存，是否放弃本次修改？",
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            != QMessageBox.Discard
        ):
            return
        if self.embedded:
            self.reload_requested.emit()
        else:
            super().reject()

    def close_jobs(self, timeout=3.0):
        self._jobs.close(timeout=timeout)
