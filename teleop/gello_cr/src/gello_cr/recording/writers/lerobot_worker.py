"""Shared official LeRobot episode service and collection evidence."""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from gello_cr.data_contract import ACTION_DIM, recording_fields

from ..protocol import MAX_IMAGE_DIMENSION
from .lerobot_v3_schema import LEROBOT_IMAGE_FEATURE_KEYS


class LeRobotWorkerService:
    """Stateful implementation of worker operations."""

    def __init__(
        self,
        dataset_factory: Callable[..., Any],
        encoder_factory: Callable[..., Any],
    ) -> None:
        self._dataset_factory = dataset_factory
        self._encoder_factory = encoder_factory
        self.dataset: Any = None
        self.buffered_frames = 0
        self.saved_episodes = 0
        self.image_shape = (0, 0, 3)
        self.sample_metadata: list[dict[str, Any]] = []
        self._finalized = False

    def handle_request(
        self,
        request: dict[str, Any],
        raw: bytes,
    ) -> tuple[dict[str, Any], bool]:
        operation = request.get("op")

        if operation == "init":
            return self._init_dataset(request), False
        if operation == "add_frame":
            return self._add_frame(request, raw), False
        if operation == "save_episode":
            return self._save_episode(request), False
        if operation == "clear_episode":
            return self._clear_episode(), False
        if operation == "finalize":
            return self._finalize(), True

        raise ValueError(f"Unknown worker operation: {operation}")

    def _init_dataset(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.dataset is not None:
            raise RuntimeError("Dataset is already initialized")

        root = Path(str(request["root"])).expanduser().resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Dataset directory is not empty: {root}")

        fps = int(request["fps"])
        height = int(request["height"])
        width = int(request["width"])
        if any(value < 2 or value > MAX_IMAGE_DIMENSION or value % 2 for value in (height, width)):
            raise ValueError("Recording image height/width must be even and within 2..2160")

        self.recording_mode = request.get("recording_mode", "tcp")
        self.state_fields, _ = recording_fields(self.recording_mode)
        self.dataset = self._create_dataset(request, root, fps, height, width)
        self.image_shape = (height, width, 3)
        if "session_metadata" in request:
            manifest = root / "meta" / "collection" / "session.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    request["session_metadata"], ensure_ascii=False, indent=2, allow_nan=False
                )
                + "\n",
                encoding="utf-8",
            )
        return {"ok": True, "root": str(root)}

    def _create_dataset(self, request, root, fps, height, width):
        raise NotImplementedError

    def _add_frame(
        self,
        request: dict[str, Any],
        raw: bytes,
    ) -> dict[str, Any]:
        if self.dataset is None:
            raise RuntimeError("Dataset is not initialized")

        if request.get("recording_mode", "tcp") != self.recording_mode:
            raise ValueError("Recording mode differs from dataset session")
        expected_per_image = int(np.prod(self.image_shape))
        expected = expected_per_image * len(LEROBOT_IMAGE_FEATURE_KEYS)
        if len(raw) != expected:
            raise ValueError(f"3-stream RGB payload is {len(raw)} bytes, expected {expected}")

        images = (
            np.frombuffer(raw, dtype=np.uint8)
            .reshape((len(LEROBOT_IMAGE_FEATURE_KEYS), *self.image_shape))
            .copy()
        )
        state = np.asarray(request["state"], dtype=np.float32)
        action = np.asarray(request["action"], dtype=np.float32)

        if state.shape != (len(self.state_fields),) or action.shape != (ACTION_DIM,):
            raise ValueError(f"Invalid state/action shapes: {state.shape}/{action.shape}")

        if not np.isfinite(state).all() or not np.isfinite(action).all():
            raise ValueError("State/action contains non-finite values")
        if not str(request["task"]).strip():
            raise ValueError("task cannot be empty")
        metadata = dict(request.get("sample_metadata", {}))
        # IPC is an external boundary: reject NaN/Inf before adding any frame.
        json.dumps(metadata, allow_nan=False)
        frame = {
            LEROBOT_IMAGE_FEATURE_KEYS[index]: images[index]
            for index in range(len(LEROBOT_IMAGE_FEATURE_KEYS))
        }
        frame.update(
            {
                "observation.state": state,
                "action": action,
                "task": str(request["task"]),
            }
        )
        self.dataset.add_frame(frame)
        self.sample_metadata.append(metadata)
        self.buffered_frames += 1
        return {"ok": True, "frames": self.buffered_frames}

    def _save_episode(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.dataset is None or self.buffered_frames <= 0:
            raise RuntimeError("No Episode frames to save")

        # Preserve legacy ordering: diagnostics first, dataset commit second.
        # If sidecar writing fails, dataset.save_episode() is not called.
        collection_dir = Path(self.dataset.root) / "meta" / "collection"
        collection_dir.mkdir(parents=True, exist_ok=True)
        collection = dict(request["collection"])
        collection["recording_mode"] = self.recording_mode
        collection["episode_index"] = self.saved_episodes
        collection["frame_count"] = self.buffered_frames
        collection["samples"] = self.sample_metadata
        streams = collection.get("camera_streams")
        collection["image_streams"] = (
            {stream["name"]: stream["feature_key"] for stream in streams}
            if streams
            else dict(
                zip(("Base RGB", "Wrist RGB", "Base ROI"), LEROBOT_IMAGE_FEATURE_KEYS, strict=True)
            )
        )
        (collection_dir / f"episode_{self.saved_episodes:06d}.json").write_text(
            json.dumps(
                collection,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

        self.dataset.save_episode()
        self.saved_episodes += 1
        self.buffered_frames = 0
        self.sample_metadata = []
        return {"ok": True, "episodes": self.saved_episodes}

    def _clear_episode(self) -> dict[str, Any]:
        if self.dataset is not None and self.buffered_frames:
            self.dataset.clear_episode_buffer()
        self.buffered_frames = 0
        self.sample_metadata = []
        return {"ok": True}

    def _finalize(self) -> dict[str, Any]:
        if self.dataset is not None:
            if self.buffered_frames:
                raise RuntimeError("Unsaved Episode; save or discard explicitly")
            self.dataset.finalize()
            self._finalized = True
        return {"ok": True, "episodes": self.saved_episodes}

    def finalize_best_effort(self) -> None:
        """Preserve the legacy worker-finally cleanup behavior."""

        if self.dataset is not None and not self._finalized:
            try:
                self.dataset.finalize()
            except Exception:
                traceback.print_exc()
