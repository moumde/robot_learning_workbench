from dataclasses import replace

import numpy as np
import pytest

from gello_cr.recording.frame import CaptureFrame
from gello_cr.recording.schema import IMAGE_KEYS, recording_schema
from gello_cr.recording.validation import CaptureValidationError, validate_capture_frame


def frame(mode="tcp", timestamp=1.0):
    schema = recording_schema(mode)
    return CaptureFrame(
        timestamp,
        (0.0,) * len(schema.observation_fields),
        (0.0,) * 12,
        {key: np.zeros((2, 2, 3), dtype=np.uint8) for key in IMAGE_KEYS},
        metadata={"recording_mode": mode, "quality": {}},
    )


@pytest.mark.parametrize("mode", ["tcp", "joint"])
def test_capture_contract_retains_training_dimensions_and_optional_raw_fields(mode):
    value = replace(frame(mode), robot_joint_state=(0.1,) * 6, robot_joint_command=(0.2,) * 6)
    validate_capture_frame(value, recording_schema(mode))
    assert value.robot_joint_state != value.robot_joint_command
    assert value.images.keys() == set(IMAGE_KEYS)


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": float("nan")},
        {"action": (0.0,) * 11},
        {"observation_state": (float("inf"),) * 18},
        {"images": {}},
        {"images": {key: np.zeros((2, 2)) for key in IMAGE_KEYS}},
    ],
)
def test_invalid_capture_is_rejected(change):
    with pytest.raises(CaptureValidationError):
        validate_capture_frame(replace(frame(), **change), recording_schema("tcp"))


def test_capture_time_must_advance_between_written_frames():
    with pytest.raises(CaptureValidationError, match="increase"):
        validate_capture_frame(
            frame(timestamp=1.0), recording_schema("tcp"), previous_timestamp=1.0
        )
