"""UTC console output and bounded, persistent logs in the parent repository."""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import workbench_root

_LOGGERS = (
    "workbench", "teleop.gello_cr", "vendor", "cr3_o6_workflow",
    "cr3_o6_policy_deploy", "cr3_o6_trajectory_replay", "cr3_o6_ptp_replay",
)
_FILE_HANDLER = "teleop-persistent-log"
_CONSOLE_HANDLER = "teleop-console"


def configure_logging(level="INFO", *, repo_root: str | Path | None = None):
    """Initialize before config/device startup; repeated calls reuse the destination."""
    root = workbench_root() if repo_root is None else workbench_root(repo_root)
    path = root / "logs" / "teleop.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    loggers = [logging.getLogger(name) for name in _LOGGERS]
    existing = {handler for logger in loggers for handler in logger.handlers}
    file_handler = next((handler for handler in existing
                         if handler.name == _FILE_HANDLER
                         and Path(handler.baseFilename) == path), None)
    for handler in existing:
        if handler.name == _FILE_HANDLER and handler is not file_handler:
            for logger in loggers:
                logger.removeHandler(handler)
            handler.close()
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s")
    formatter.converter = time.gmtime
    if file_handler is None:
        file_handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024,
                                          backupCount=5, encoding="utf-8")
        file_handler.name = _FILE_HANDLER
        file_handler.setFormatter(formatter)
    console = next((handler for handler in existing if handler.name == _CONSOLE_HANDLER), None)
    if console is None:
        console = logging.StreamHandler()
        console.name = _CONSOLE_HANDLER
        console.setFormatter(formatter)
    console.setLevel(level)
    # Console verbosity may be raised to CRITICAL; failures still belong in the file.
    effective_level = min(console.level, logging.ERROR)
    file_handler.setLevel(effective_level)
    for logger in loggers:
        if console not in logger.handlers:
            logger.addHandler(console)
        if file_handler not in logger.handlers:
            logger.addHandler(file_handler)
        logger.setLevel(effective_level)
        logger.propagate = False
