"""Validate canonical capture data without any storage-format dependencies."""

import math

import numpy as np

from .errors import CaptureValidationError
from .frame import CaptureFrame
from .schema import RecordingSchema

RAW_FIELDS = (
    "robot_joint_state",
    "robot_joint_command",
    "robot_tcp_state",
    "robot_tcp_command",
    "hand_state",
    "hand_command",
)


def validate_capture_frame(
    frame: CaptureFrame, schema: RecordingSchema, *, previous_timestamp=None
):
    if not math.isfinite(frame.timestamp) or frame.timestamp < 0:
        raise CaptureValidationError("Capture timestamp must be finite and nonnegative")
    if previous_timestamp is not None and frame.timestamp <= previous_timestamp:
        raise CaptureValidationError("Capture timestamps must increase strictly")
    for name, expected in (
        ("observation_state", len(schema.observation_fields)),
        ("action", len(schema.action_fields)),
    ):
        values = np.asarray(getattr(frame, name))
        if (
            values.shape != (expected,)
            or not np.issubdtype(values.dtype, np.number)
            or not np.isfinite(values).all()
        ):
            raise CaptureValidationError(f"{name} requires {expected} finite values")
    for key in schema.image_keys:
        image = frame.images.get(key)
        if (
            not isinstance(image, np.ndarray)
            or image.ndim != 3
            or image.shape[2] != 3
            or not image.size
            or not np.issubdtype(image.dtype, np.number)
            or not np.isfinite(image).all()
        ):
            raise CaptureValidationError(f"Camera RGB frame {key} must be finite HxWx3")
    for name in RAW_FIELDS:
        values = getattr(frame, name)
        if values is not None and (
            np.asarray(values).shape != (6,) or not np.isfinite(values).all()
        ):
            raise CaptureValidationError(f"{name} requires six finite values")
    for key, value in frame.metadata.get("quality", {}).items():
        if not math.isfinite(float(value)):
            raise CaptureValidationError(f"Quality {key} is non-finite")
