"""LeRobot V3 writer using the official SDK in a dedicated worker."""

from .base import WriterCapabilities
from .frame_mapping import prepare_frame, resize_rgb_for_openpi
from .lerobot_v3_schema import (
    LEGACY_SAMPLE_IMAGE_KEYS,
    LEROBOT_IMAGE_FEATURE_KEYS,
    dataset_features,
)
from .worker_writer import WorkerDatasetWriter

__all__ = [
    "LeRobotV3Writer",
    "LEROBOT_IMAGE_FEATURE_KEYS",
    "LEGACY_SAMPLE_IMAGE_KEYS",
    "dataset_features",
    "prepare_frame",
    "resize_rgb_for_openpi",
]


class LeRobotV3Writer(WorkerDatasetWriter):
    format_name = "lerobot_v3"
    capabilities = WriterCapabilities(True, False, True, True)
