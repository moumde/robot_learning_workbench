"""Combined training and deployment desktop application."""

from __future__ import annotations

import sys

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from hmi.deploy.app import MainWindow as DeployWindow
from hmi.trainui.controller import TrainController
from hmi.trainui.styles import STYLE_SHEET
from hmi.trainui.views.main_window import MainWindow as TrainWindow


class WorkbenchWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Robot Learning Workbench")
        self.resize(1460, 980)
        self.setMinimumSize(1120, 760)
        self._close_pending = False

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        self.train_window = TrainWindow()
        self.deploy_window = DeployWindow()
        for window in (self.train_window, self.deploy_window):
            window.setParent(self.tabs)
            window.setWindowFlags(Qt.WindowType.Widget)

        self.tabs.addTab(self.train_window, "训练")
        self.tabs.addTab(self.deploy_window, "部署")

        self.train_controller = TrainController(self.train_window)
        # Keep the controller alive for the entire Qt application lifetime.
        self.train_window._train_controller = self.train_controller

        self._close_timer = QTimer(self)
        self._close_timer.setInterval(250)
        self._close_timer.timeout.connect(self._finish_deferred_close)

    def start(self) -> None:
        self.train_controller.start()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        # Let deployment perform its existing confirmation and graceful stop
        # sequence before shutting down the training-side background workers.
        self.deploy_window.close()
        if self._deployment_is_running():
            if self.deploy_window.close_after_stop:
                self._close_pending = True
                self._close_timer.start()
            event.ignore()
            return

        if not self.train_window.close_handler():
            self.deploy_window.show()
            event.ignore()
            return

        self._close_pending = False
        self._close_timer.stop()
        event.accept()

    def _finish_deferred_close(self) -> None:
        if self._close_pending and not self._deployment_is_running():
            self._close_pending = False
            self._close_timer.stop()
            QTimer.singleShot(0, self.close)

    def _deployment_is_running(self) -> bool:
        return any(
            process is not None and process.state() != QProcess.ProcessState.NotRunning
            for process in (self.deploy_window.task_process, self.deploy_window.server_process)
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Robot Learning Workbench")
    app.setStyleSheet(STYLE_SHEET)

    window = WorkbenchWindow()
    window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
