import dataclasses
from typing import ClassVar

import einops
import numpy as np

from openpi import transforms


def _parse_image(image) -> np.ndarray:
    """Convert LeRobot image format to OpenPI image format.

    LeRobot video decoding returns images as [C, H, W] float32 arrays in
    [0, 1], while OpenPI expects [H, W, C] uint8 arrays in [0, 255].
    """
    image = np.asarray(image)

    if np.issubdtype(image.dtype, np.floating):
        image = (255 * image).astype(np.uint8)

    if image.shape[0] == 3:
        image = einops.rearrange(image, "c h w -> h w c")

    return image


@dataclasses.dataclass(frozen=True)
class CR3O6Inputs(transforms.DataTransformFn):
    """Input transform for Dobot CR3 + LinkerHand O6.

    Expected input after RepackTransform has three image names, a 12D state,
    optional 12D actions, and an optional language prompt. The state/action
    layout is six CR3 joints followed by six O6 hand values.
    """

    EXPECTED_CAMERAS: ClassVar[tuple[str, ...]] = (
        "base_0_rgb",
        "left_wrist_0_rgb",
        "right_wrist_0_rgb",
    )

    def __call__(self, data: dict) -> dict:
        in_images = data["images"]

        unexpected = set(in_images) - set(self.EXPECTED_CAMERAS)
        if unexpected:
            raise ValueError(
                f"Unexpected camera names: {unexpected}. "
                f"Expected cameras: {self.EXPECTED_CAMERAS}"
            )

        if "base_0_rgb" not in in_images:
            raise ValueError("CR3O6 policy requires base_0_rgb camera.")

        base_image = _parse_image(in_images["base_0_rgb"])
        images = {"base_0_rgb": base_image}
        image_masks = {"base_0_rgb": np.True_}

        # Wrist cameras are optional at the transform level. Missing cameras
        # are represented by black images and disabled masks.
        for camera_name in ("left_wrist_0_rgb", "right_wrist_0_rgb"):
            if camera_name in in_images:
                images[camera_name] = _parse_image(in_images[camera_name])
                image_masks[camera_name] = np.True_
            else:
                images[camera_name] = np.zeros_like(base_image)
                image_masks[camera_name] = np.False_

        inputs = {
            "image": images,
            "image_mask": image_masks,
            "state": np.asarray(data["state"]),
        }

        if "actions" in data:
            actions = np.asarray(data["actions"])
            if actions.shape[-1] != 12:
                raise ValueError(
                    f"Expected 12D CR3+O6 actions, got shape {actions.shape}"
                )
            inputs["actions"] = actions

        if "prompt" in data:
            inputs["prompt"] = data["prompt"]

        return inputs


@dataclasses.dataclass(frozen=True)
class CR3O6Outputs(transforms.DataTransformFn):
    """Convert Pi05 model actions to the physical CR3/O6 action contract."""

    def __call__(self, data: dict) -> dict:
        actions = np.asarray(data["actions"], dtype=np.float32)

        if actions.ndim == 0 or actions.shape[-1] < 12:
            raise ValueError(
                "Expected model actions with at least 12 dimensions, "
                f"got shape {actions.shape}"
            )
        if not np.all(np.isfinite(actions)):
            raise ValueError("CR3/O6 model actions contain NaN or Inf")

        # Pi05 has a 32D action head; the physical CR3/O6 interface uses 12D.
        return {"actions": actions[..., :12].copy()}
