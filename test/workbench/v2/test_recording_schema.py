from __future__ import annotations

import math

import numpy as np
import pytest

from core.workbench.data_contract import ACTION_FIELDS, STATE_FIELDS
from dataclasses import replace
from core.workbench.recording.frame import CaptureFrame
from core.workbench.recording.schema import IMAGE_KEYS, recording_schema
from core.workbench.recording.validation import validate_capture_frame
from core.workbench.recording.writers.lerobot_v3 import LEROBOT_IMAGE_FEATURE_KEYS, dataset_features


def _sample():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    return CaptureFrame(10.0, (0.0,) * 18, (0.0,) * 12, {key: image for key in IMAGE_KEYS})


def test_canonical_image_names_are_format_independent():
    assert IMAGE_KEYS == ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")


def test_valid_sample_passes():
    validate_capture_frame(_sample(), recording_schema("tcp"))


def test_sample_rejects_wrong_state_and_action_dimensions():
    with pytest.raises(ValueError, match="18"):
        validate_capture_frame(
            replace(_sample(), observation_state=(0.0,) * 17), recording_schema("tcp")
        )
    with pytest.raises(ValueError, match="12"):
        validate_capture_frame(replace(_sample(), action=(0.0,) * 11), recording_schema("tcp"))


def test_sample_rejects_nonfinite_state_or_action():
    with pytest.raises(ValueError, match="finite"):
        validate_capture_frame(replace(_sample(), action=(math.inf,) * 12), recording_schema("tcp"))


def test_sample_rejects_non_rgb_shape():
    sample = _sample()
    sample.images["right_wrist_0_rgb"] = np.zeros((100, 100), dtype=np.uint8)
    with pytest.raises(ValueError, match="right_wrist_0_rgb"):
        validate_capture_frame(sample, recording_schema("tcp"))


def test_dataset_features_use_frozen_state_and_action_names() -> None:
    features = dataset_features(224, 224)

    assert features["observation.state"]["shape"] == (18,)
    assert features["observation.state"]["names"] == list(STATE_FIELDS)
    assert features["action"]["shape"] == (12,)
    assert features["action"]["names"] == list(ACTION_FIELDS)


def test_dataset_features_preserve_existing_serialized_image_names() -> None:
    features = dataset_features(224, 224)

    assert LEROBOT_IMAGE_FEATURE_KEYS == (
        "observation.images.base_0_rgb",
        "observation.images.left_wrist_0_rgb",
        "observation.images.right_wrist_0_rgb",
    )
    for key in LEROBOT_IMAGE_FEATURE_KEYS:
        assert features[key] == {
            "dtype": "video",
            "shape": (224, 224, 3),
            "names": ["height", "width", "channel"],
        }


def test_dataset_features_reject_invalid_image_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        dataset_features(0, 224)
