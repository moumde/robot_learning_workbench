"""Actual offscreen Qt interactions for trajectory selection and process handoff."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from hmi.deploy import app as hmi

# isort: split

from gello_cr.trajectory import TrajectoryFrame, TrajectoryStore, make_trajectory


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_shared_task_dialog_roundtrips_named_trajectory_and_explicit_hand_choice(qt_app, tmp_path):
    value = make_trajectory(
        "joint plan", [TrajectoryFrame(0, robot_joint_command=(0,) * 6)], hand_type=None
    )
    directory = TrajectoryStore(tmp_path).save(value)
    dialog = hmi.TaskDialog()
    dialog.kind.setCurrentIndex(dialog.kind.findData("trajectory"))
    dialog.dataset.setText(str(directory))
    task = dialog.task()
    assert task.kind == "trajectory" and not task.hand_enabled
    assert dialog.time_scale.maximum() == 2.0
    restored = hmi._deserialize_workflow({"version": 1, "tasks": [hmi._serialize_task(task)]})
    assert restored == [task]
    dialog.hand_enabled.setChecked(True)
    assert dialog.task().hand_enabled
    dialog.close()


class Process(QObject):
    readyReadStandardOutput = Signal()
    readyReadStandardError = Signal()
    finished = Signal(int, object)
    errorOccurred = Signal(object)
    ProcessError = QProcess.ProcessError
    ProcessState = QProcess.ProcessState
    ExitStatus = QProcess.ExitStatus

    def __init__(self, parent=None):
        super().__init__(parent)
        self.started = False

    def setProgram(self, value):
        self.program = value

    def setArguments(self, value):
        self.arguments = value

    def setWorkingDirectory(self, value):
        self.directory = value

    def setProcessEnvironment(self, value):
        self.environment = value

    def start(self):
        self.started = True

    def state(self):
        return self.ProcessState.Running


def test_hmi_hands_off_profile_and_blocks_competing_workflow_until_collection_closes(
    qt_app, monkeypatch
):
    monkeypatch.setattr(hmi, "QProcess", Process)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[1]))
    window = hmi.MainWindow()
    profile = window._selected_hardware()
    window.task_process = object()
    window._start_teleop()
    assert window.teleop_process is None
    assert warnings == ["工作流正在运行"]
    window.task_process = None
    window._start_teleop()
    process = window.teleop_process
    assert process.started
    assert process.arguments == [
        str(hmi.ROOT / "scripts/run_teleop.sh"),
        "--hardware-config",
        str(profile),
    ]
    assert not window.run_button.isEnabled()
    window.tasks = [hmi.Task("ptp", "test", dataset_dir=Path("unused"))]
    window._run_plan()
    assert warnings[-1] == "遥操窗口正在运行"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)

    class Close:
        ignored = False

        def ignore(self):
            self.ignored = True

    close = Close()
    window.closeEvent(close)
    assert close.ignored and window.close_after_stop
    assert window.teleop_process is process  # No signal bypasses pending-data decisions.
    process.finished.emit(0, QProcess.ExitStatus.NormalExit)
    assert window.teleop_process is None
    assert window.run_button.isEnabled() and window.teleop_button.isEnabled()
    qt_app.processEvents()
    window.close()
