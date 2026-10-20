"""LeRobot V2.1 writer; the worker must use the official v0.3.3 SDK."""

from .base import WriterCapabilities
from .worker_writer import WorkerDatasetWriter


class LeRobotV21Writer(WorkerDatasetWriter):
    format_name = "lerobot_v21"
    capabilities = WriterCapabilities(True, False, True, True)
