"""Dataset browsing/validation and P6 recovery, through application commands."""

from PySide6.QtWidgets import QTableWidgetItem, QWidget

from teleop.gello_cr.core.state_machine import Command

from ..generated.ui_dataset_manager_page import Ui_DatasetManagerPage
from ..recovery_panel import RecoveryPanel


class DatasetManagerPage(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self.submit = submit
        self._signature = None
        self._busy = False
        self._ui = Ui_DatasetManagerPage()
        self._ui.setupUi(self)
        self.root_edit = self._ui.dataset_root_edit
        self.scan_button = self._ui.dataset_scan_button
        self.validate_button = self._ui.dataset_validate_button
        self.active_label = self._ui.dataset_active_label
        self.table = self._ui.dataset_table
        self.details = self._ui.dataset_details
        self.table.horizontalHeader().setStretchLastSection(True)
        self.recovery = RecoveryPanel(submit, self._ui.dataset_recovery)
        self._ui.dataset_recovery_layout.addWidget(self.recovery)
        self.scan_button.clicked.connect(
            lambda: submit(Command.LIST_DATASETS, {"root": self.root_edit.text().strip()})
        )
        self.validate_button.clicked.connect(self._validate)
        self.table.itemSelectionChanged.connect(self._details)
        self._items = []

    def _selected(self):
        row = self.table.currentRow()
        return self._items[row] if 0 <= row < len(self._items) else None

    def _validate(self):
        item = self._selected()
        if item:
            self.submit(Command.VALIDATE_DATASET, {"path": item["path"]})

    def _details(self):
        item = self._selected()
        self.validate_button.setEnabled(item is not None and not self._busy)
        if item is None:
            self.details.clear()
            return
        report = item.get("validation")
        text = item["path"] + "\n" + item.get("error", "")
        if report:
            text += "\nValidation: " + ("PASS" if report["valid"] else "FAILED")
            text += "\n" + "\n".join(report["errors"] + report["warnings"])
        else:
            text += "\nUNCHECKED：尚未在本次会话校验。"
        self.details.setPlainText(text)

    def render(self, catalog, dataset, busy):
        self._busy = busy
        if not self.root_edit.text():
            self.root_edit.setText(catalog.get("root") or dataset.get("output_root", ""))
        items = catalog.get("items", [])
        signature = repr(items)
        if signature != self._signature:
            selected = (self._selected() or {}).get("path")
            self._signature, self._items = signature, items
            self.table.setRowCount(len(items))
            for row, item in enumerate(items):
                values = [
                    item.get("task") or item["name"],
                    item["format"],
                    item.get("episodes"),
                    item.get("frames"),
                    item.get("created_at", ""),
                    item["status"],
                ]
                for col, value in enumerate(values):
                    self.table.setItem(
                        row, col, QTableWidgetItem("—" if value is None else str(value))
                    )
                if selected == item["path"]:
                    self.table.selectRow(row)
            self.table.resizeColumnsToContents()
            self._details()
        self.active_label.setText(
            (
                f"IN_PROGRESS · {dataset.get('batch_task', '')} · {dataset.get('format', '')} · "
                f"Batch {dataset['batch_id'][:8]}"
            )
            if dataset.get("batch_id")
            else "当前没有正在采集的批次"
        )
        self.scan_button.setEnabled(not busy)
        self.validate_button.setEnabled(not busy and self._selected() is not None)
        self.recovery.render(dataset, busy=busy)
