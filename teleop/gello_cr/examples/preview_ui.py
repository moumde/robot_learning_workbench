"""No-hardware preview launcher for the Workbench shell.

This preview deliberately does not import or instantiate NRC/GELLO/O6/cameras.
Command requests are logged to stdout and do not change application state.
"""

from __future__ import annotations

import logging
import sys

from gello_cr.app import ApplicationService
from gello_cr.ui.command_port import CallbackCommandPort
from gello_cr.ui.main_window import OperatorMainWindow
from gello_cr.ui.presenter import OperatorUiPresenter


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit(
            "PySide6 is not installed. Install the project UI extra before "
            "running the Workbench preview."
        ) from exc

    app = QApplication(sys.argv)
    service = ApplicationService()

    presenter = OperatorUiPresenter(
        service,
        runtime_snapshot=lambda: {"state": "idle"},
        recorder_snapshot=lambda: {
            "session_active": False,
            "episode_active": False,
            "buffered_frames": 0,
            "saved_episodes": 0,
            "error": "",
            "quality": {"needs_review": False},
        },
    )

    def log_request(request) -> None:
        logging.getLogger("workbench.example").info(
            "command=%s payload=%s", request.command.name, dict(request.payload)
        )

    window = OperatorMainWindow(
        presenter,
        CallbackCommandPort(log_request),
    )
    window.setWindowTitle("Robot Learning Workbench — UI Preview (No Hardware)")
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
