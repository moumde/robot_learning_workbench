"""Recovery decisions over application commands; no filesystem or SDK access."""

from PySide6.QtWidgets import QMessageBox, QWidget

from gello_cr.core.state_machine import Command

from .generated.ui_recovery_panel import Ui_RecoveryPanel


class RecoveryPanel(QWidget):
    def __init__(self, submit, parent=None):
        super().__init__(parent)
        self.submit = submit
        self.snapshot = {}
        self._signature = None
        self._partial_signature = None
        self._busy = False
        self._ui = Ui_RecoveryPanel()
        self._ui.setupUi(self)
        self.batches = self._ui.recovery_batches
        self.summary = self._ui.recovery_summary
        self.refresh_button = self._ui.recovery_refresh_button
        self.resume_button = self._ui.recovery_resume_button
        self.finalize_button = self._ui.recovery_finalize_button
        self.discard_button = self._ui.recovery_discard_button
        self.partials = self._ui.recovery_partials
        self.failure_button = self._ui.recovery_failure_button
        self.discard_partial_button = self._ui.recovery_discard_partial_button
        self.suspend_button = self._ui.recovery_suspend_button
        self.discard_current_button = self._ui.recovery_discard_current_button
        self.batches.currentIndexChanged.connect(self._details)
        self.partials.currentIndexChanged.connect(self._partial_buttons)
        self.refresh_button.clicked.connect(lambda: self.submit(Command.SCAN_RECOVERABLE_BATCHES))
        self.resume_button.clicked.connect(lambda: self._batch_command(Command.RESUME_BATCH))
        self.finalize_button.clicked.connect(lambda: self._batch_command(Command.FINALIZE_BATCH))
        self.discard_button.clicked.connect(lambda: self._discard(self._selected_id()))
        self.failure_button.clicked.connect(lambda: self._resolve("failure"))
        self.discard_partial_button.clicked.connect(lambda: self._resolve("discard"))
        self.suspend_button.clicked.connect(self._suspend)
        self.discard_current_button.clicked.connect(
            lambda: self._discard(self.snapshot.get("batch_id"))
        )

    def _selected(self):
        return self.batches.currentData() or {}

    def _selected_id(self):
        return self._selected().get("batch_id", "")

    def _batch_command(self, command):
        self.submit(command, {"batch_id": self._selected_id()})

    def _discard(self, batch_id):
        if (
            batch_id
            and QMessageBox.question(
                self,
                "丢弃批次",
                "将整个批次标记为丢弃？原始 staging 文件会保留。",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            == QMessageBox.Yes
        ):
            self.submit(Command.DISCARD_BATCH, {"batch_id": batch_id})

    def _suspend(self):
        if self.snapshot.get("episode_active") or self.snapshot.get("buffered_frames"):
            choice = QMessageBox.question(
                self,
                "保留未完成采集",
                "停止本次录制并保留为 Partial？下次需选择丢弃或 Failure。",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if choice != QMessageBox.Yes:
                return
        self.submit(Command.SUSPEND_BATCH)

    def _partial_context(self):
        if self.snapshot.get("batch_id"):
            return self.snapshot["batch_id"], self.snapshot.get("partial_episodes", [])
        selected = self._selected()
        return selected.get("batch_id", ""), selected.get("partial_episodes", [])

    def _resolve(self, decision):
        episode = self.partials.currentData()
        if episode is not None:
            self.submit(
                Command.RESOLVE_PARTIAL_EPISODE,
                {
                    "batch_id": self._partial_context()[0],
                    "episode_index": episode["episode_index"],
                    "decision": decision,
                },
            )

    def _partial_buttons(self):
        episode = self.partials.currentData()
        self.failure_button.setEnabled(
            not self._busy and episode is not None and episode["frame_count"] > 0
        )
        self.discard_partial_button.setEnabled(not self._busy and episode is not None)

    def _details(self):
        selected = self._selected()
        if selected:
            status = "INVALID" if selected.get("status") == "failed" else "RECOVERABLE"
            self.summary.setText(
                f"{status} · {selected['task_name']} · {selected['dataset_format']} · "
                f"{selected['episodes']} Episodes · {selected['segments']} Segments\n"
                + selected.get("created_at", "")
                + " · "
                + selected["batch_id"][:8]
                + ("\n" + selected["error"] if selected.get("error") else "")
            )
        else:
            self.summary.setText("没有未完成批次")
        allowed = bool(selected) and not self.snapshot.get("batch_id") and not self._busy
        self.resume_button.setEnabled(allowed)
        self.finalize_button.setEnabled(allowed)
        self.discard_button.setEnabled(allowed)
        batch_id, records = self._partial_context()
        signature = (batch_id, repr(records))
        if signature != self._partial_signature:
            previous = (
                (self.partials.currentData() or {}).get("episode_index")
                if self._partial_signature and self._partial_signature[0] == batch_id
                else None
            )
            self.partials.blockSignals(True)
            self.partials.clear()
            for record in records:
                self.partials.addItem(
                    f"Episode {record['episode_index']} · Partial · {record['frame_count']} frames",
                    record,
                )
                if record["episode_index"] == previous:
                    self.partials.setCurrentIndex(self.partials.count() - 1)
            self.partials.blockSignals(False)
            self._partial_signature = signature
        self._partial_buttons()

    def render(self, snapshot, *, busy=False):
        self.snapshot, self._busy = snapshot, busy
        rows = snapshot.get("recoverable_batches", [])
        signature = repr(rows)
        if signature != self._signature:
            previous = self._selected_id()
            self.batches.blockSignals(True)
            self.batches.clear()
            for row in rows:
                self.batches.addItem(
                    f"{row['task_name']} · {row['dataset_format']} · {row['batch_id'][:8]}", row
                )
                if row["batch_id"] == previous:
                    self.batches.setCurrentIndex(self.batches.count() - 1)
            self.batches.blockSignals(False)
            self._signature = signature
        self.batches.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        active = bool(snapshot.get("batch_id")) and not busy
        self.suspend_button.setEnabled(active)
        self.discard_current_button.setEnabled(active)
        self._details()
