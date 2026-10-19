from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from hmi.trainui.controller import TrainController
from hmi.trainui.styles import STYLE_SHEET
from hmi.trainui.views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("机器人学习工作台 - 训练界面")
    app.setStyleSheet(STYLE_SHEET)

    window = MainWindow()
    controller = TrainController(window)
    # Keep the controller alive for the entire Qt application lifetime.
    window._train_controller = controller
    window.show()
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
