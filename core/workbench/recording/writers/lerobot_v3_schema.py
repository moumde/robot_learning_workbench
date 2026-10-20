"""V3 feature names and shapes, shared by the worker and format validator."""

from typing import Any

from core.workbench.data_contract import ACTION_DIM, recording_fields

from ..schema import IMAGE_KEYS

LEROBOT_IMAGE_FEATURE_KEYS = tuple(f"observation.images.{key}" for key in IMAGE_KEYS)
LEGACY_SAMPLE_IMAGE_KEYS = ("image_base_rgb", "image_wrist_rgb", "image_roi_rgb")


def dataset_features(
    height: int, width: int, recording_mode: str = "tcp"
) -> dict[str, dict[str, Any]]:
    state_fields, action_fields = recording_fields(recording_mode)
    height_value = int(height)
    width_value = int(width)
    if height_value <= 0 or width_value <= 0:
        raise ValueError("dataset image height/width must be positive")

    features: dict[str, dict[str, Any]] = {
        "observation.state": {
            "dtype": "float32",
            "shape": (len(state_fields),),
            "names": list(state_fields),
        },
        "action": {
            "dtype": "float32",
            "shape": (ACTION_DIM,),
            "names": list(action_fields),
        },
    }

    for feature_key in LEROBOT_IMAGE_FEATURE_KEYS:
        features[feature_key] = {
            "dtype": "video",
            "shape": (height_value, width_value, 3),
            "names": ["height", "width", "channel"],
        }

    return features
