"""Errors shared by capture, sessions, and writer implementations."""

from core.workbench.errors import RecordingError as RecordingError


class CaptureValidationError(RecordingError, ValueError):
    pass


class WriterError(RecordingError):
    pass


class WriterStateError(WriterError):
    pass


class DatasetFinalizeError(WriterError):
    pass


class UnsupportedDatasetFormat(WriterError):
    pass
