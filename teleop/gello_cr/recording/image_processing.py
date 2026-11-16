"""Pure image transforms used by recording and UI compatibility layers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class RoiCrop:
    """Result of a normalized RGB ROI crop."""

    bounds_px: tuple[int, int, int, int]
    image_rgb: np.ndarray


def normalized_roi_bounds(
    image_rgb: np.ndarray,
    roi_norm: Sequence[float],
) -> tuple[int, int, int, int]:
    """Convert normalized ROI coordinates to clamped pixel bounds.

    This intentionally preserves the legacy Qt semantics exactly:

    - normalized coordinates are multiplied by width/height;
    - Python ``round`` is applied before integer conversion;
    - left/top are clamped to the last valid source pixel;
    - right/bottom are clamped to the image edge;
    - the result is forced to contain at least one pixel.

    The function therefore preserves existing dataset framing while moving the
    calculation out of the UI.
    """

    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("ROI source must be an HxWx3 RGB image")

    height, width = int(image.shape[0]), int(image.shape[1])
    if height <= 0 or width <= 0:
        raise ValueError("ROI source width/height must be positive")

    values = tuple(float(value) for value in roi_norm)
    if len(values) != 4:
        raise ValueError("normalized ROI must contain exactly four values")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("normalized ROI values must be finite")

    x1, y1, x2, y2 = values

    left = max(0, min(width - 1, int(round(x1 * width))))
    right = max(left + 1, min(width, int(round(x2 * width))))
    top = max(0, min(height - 1, int(round(y1 * height))))
    bottom = max(top + 1, min(height, int(round(y2 * height))))

    return left, top, right, bottom


def crop_normalized_roi(
    image_rgb: np.ndarray,
    roi_norm: Sequence[float],
) -> RoiCrop:
    """Return a contiguous copy of the normalized RGB ROI."""

    image = np.asarray(image_rgb)
    bounds = normalized_roi_bounds(image, roi_norm)
    left, top, right, bottom = bounds
    crop = np.ascontiguousarray(image[top:bottom, left:right]).copy()
    return RoiCrop(bounds_px=bounds, image_rgb=crop)
