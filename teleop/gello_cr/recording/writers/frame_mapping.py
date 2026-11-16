"""Shared RGB normalization and canonical frame transport for dataset writers."""

import cv2
import numpy as np

from ..frame import CaptureFrame
from ..schema import IMAGE_KEYS, recording_schema
from ..validation import RAW_FIELDS, validate_capture_frame


def prepare_frame(frame: CaptureFrame, *, task: str, height: int, width: int, recording_mode: str):
    validate_capture_frame(frame, recording_schema(recording_mode))
    images = [resize_rgb_for_openpi(frame.images[key], height, width) for key in IMAGE_KEYS]
    sample_metadata = {
        "timestamp": float(frame.timestamp),
        "quality": {key: float(value) for key, value in frame.metadata.get("quality", {}).items()},
    }
    raw_fields = {
        key: [float(value) for value in getattr(frame, key)]
        for key in RAW_FIELDS
        if getattr(frame, key) is not None
    }
    if raw_fields:
        sample_metadata["raw"] = raw_fields
    payload = {
        "op": "add_frame",
        "recording_mode": recording_mode,
        "state": [float(value) for value in frame.observation_state],
        "action": [float(value) for value in frame.action],
        "task": task,
        "height": height,
        "width": width,
        "sample_metadata": sample_metadata,
    }
    return payload, b"".join(image.tobytes(order="C") for image in images)


def resize_rgb_for_openpi(
    image: np.ndarray,
    height: int = 224,
    width: int = 224,
) -> np.ndarray:
    """Match the existing OpenPI aspect-preserving black-padding resize.

    Input/output are HWC RGB arrays. A 640x480 frame becomes 224x168 content
    centered vertically in a 224x224 black canvas.
    """

    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"RGB image must have HxWx3 shape, got {array.shape}")

    if array.dtype != np.uint8:
        if np.issubdtype(array.dtype, np.floating):
            maximum = float(np.nanmax(array)) if array.size else 0.0
            if maximum <= 1.0:
                array = array * 255.0
        array = np.clip(array, 0, 255).astype(np.uint8)

    source_height, source_width = array.shape[:2]
    if source_height <= 0 or source_width <= 0:
        raise ValueError("RGB image is empty")

    if source_height == height and source_width == width:
        return np.ascontiguousarray(array)

    ratio = max(source_width / width, source_height / height)
    resized_height = max(1, int(source_height / ratio))
    resized_width = max(1, int(source_width / ratio))
    resized = cv2.resize(
        array,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA if ratio >= 1.0 else cv2.INTER_LINEAR,
    )

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    top = (height - resized_height) // 2
    left = (width - resized_width) // 2
    canvas[top : top + resized_height, left : left + resized_width] = resized
    return np.ascontiguousarray(canvas)
