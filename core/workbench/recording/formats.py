"""Dataset output options, independent of capture and sampling."""

import sys
from dataclasses import dataclass
from enum import Enum


class DatasetFormat(str, Enum):  # noqa: UP042 -- independent workers may use Python 3.10.
    LEROBOT_V21 = "lerobot_v21"
    LEROBOT_V3 = "lerobot_v3"
    HDF5 = "hdf5"


@dataclass(frozen=True, slots=True)
class DatasetWriterConfig:
    # Timing, dimensions and output root come from DatasetSessionMetadata.
    format: DatasetFormat = DatasetFormat.LEROBOT_V3
    worker_python: str = sys.executable
    repo_prefix: str = "local/capture"
    video_codec: str | None = None
    hdf5_compression: str | None = None
