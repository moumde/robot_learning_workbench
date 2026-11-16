"""Format-independent dataset capture and recording lifecycle."""

from .errors import (
    CaptureValidationError,
    DatasetFinalizeError,
    RecordingError,
    UnsupportedDatasetFormat,
    WriterError,
    WriterStateError,
)
from .formats import DatasetFormat, DatasetWriterConfig
from .frame import CaptureFrame
from .metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
    build_dataset_name,
)
from .schema import RecordingSchema, recording_schema
from .session import RecordingSession
from .writers.base import DatasetWriter

__all__ = [
    "CaptureFrame",
    "DatasetFormat",
    "DatasetWriterConfig",
    "RecordingSchema",
    "recording_schema",
    "RecordingSession",
    "DatasetWriter",
    "DatasetSessionMetadata",
    "EpisodeMetadata",
    "EpisodeOutcome",
    "EpisodeResult",
    "build_dataset_name",
    "RecordingError",
    "CaptureValidationError",
    "WriterError",
    "WriterStateError",
    "DatasetFinalizeError",
    "UnsupportedDatasetFormat",
]
