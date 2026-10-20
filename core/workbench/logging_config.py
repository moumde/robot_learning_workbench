"""One UTC logging configuration for the application and its domain services."""

import logging
import time


def configure_logging(level="INFO"):
    logger = logging.getLogger("workbench")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s")
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
