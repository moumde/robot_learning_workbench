"""Single-file HDF5 backend with explicit pending episode commits."""

import json
from pathlib import Path

import h5py
import numpy as np

from ..schema import IMAGE_KEYS, recording_schema

RAW_PATHS = {
    "robot_joint_state": "observation/joint",
    "robot_tcp_state": "observation/tcp",
    "hand_state": "observation/hand",
    "robot_joint_command": "action/robot_joint",
    "robot_tcp_command": "action/robot_tcp",
    "hand_command": "action/hand",
}


def write_attributes(group, values):
    for key, value in values.items():
        group.attrs[key] = (
            value
            if isinstance(value, (str, int, float, bool))
            else json.dumps(value, ensure_ascii=False, allow_nan=False)
        )


class HDF5WorkerService:
    def __init__(self):
        self.file = None
        self.frames = self.saved_episodes = 0

    def handle_request(self, request, raw):
        op = request["op"]
        if op == "init":
            if self.file is not None:
                raise RuntimeError("Dataset is already initialized")
            compression = request.get("hdf5_compression")
            if compression not in (None, "gzip", "lzf"):
                raise ValueError("HDF5 compression must be gzip, lzf or null")
            self.compression = compression
            self.mode = request["recording_mode"]
            self.schema = recording_schema(self.mode)
            self.shape = (int(request["height"]), int(request["width"]), 3)
            root = Path(request["root"])
            root.mkdir(parents=True, exist_ok=False)
            self.file = h5py.File(root / "dataset.hdf5", "x")
            write_attributes(
                self.file.create_group("metadata"),
                {
                    **request["session_metadata"],
                    "hdf5_schema_version": 1,
                    "compression": compression,
                },
            )
            self.file.create_group("episodes")
            self.file.flush()
            return {"ok": True, "root": str(root)}, False
        if self.file is None:
            raise RuntimeError("Dataset is not open")
        if op == "add_frame":
            self._add_frame(request, raw)
            return {"ok": True, "frames": self.frames}, False
        if op == "save_episode":
            if not self.frames:
                raise RuntimeError("No episode frames to save")
            metadata = {
                **request["collection"],
                "episode_index": self.saved_episodes,
                "frame_count": self.frames,
                "recording_mode": self.mode,
            }
            write_attributes(self.file["pending_episode/metadata"], metadata)
            self.file.flush()
            self.file.move("pending_episode", f"episodes/{self.saved_episodes:06d}")
            self.file.flush()
            self.saved_episodes += 1
            self.frames = 0
            return {"ok": True, "episodes": self.saved_episodes}, False
        if op == "clear_episode":
            if "pending_episode" in self.file:
                del self.file["pending_episode"]
            self.file.flush()
            self.frames = 0
            return {"ok": True}, False
        if op == "finalize":
            if "pending_episode" in self.file:
                raise RuntimeError("Save or discard the pending episode before finalize")
            self.file.flush()
            self.file.close()
            self.file = None
            return {"ok": True, "episodes": self.saved_episodes}, True
        raise ValueError(f"Unknown worker operation: {op}")

    def _create_pending(self, task):
        group = self.file.create_group("pending_episode")
        write_attributes(group.create_group("metadata"), {"task": task})
        fields = {
            "timestamp": ((), "f8"),
            "observation/state": ((len(self.schema.observation_fields),), "f4"),
            "action/value": ((len(self.schema.action_fields),), "f4"),
            **{path: ((6,), "f4") for path in RAW_PATHS.values()},
            **{f"valid/{key}": ((), "bool") for key in RAW_PATHS},
            **{f"observation/images/{key}": (self.shape, "u1") for key in IMAGE_KEYS},
            "metadata/samples": ((), h5py.string_dtype("utf-8")),
        }
        for path, (shape, dtype) in fields.items():
            parent, _, name = path.rpartition("/")
            target = group.require_group(parent) if parent else group
            options = {"compression": self.compression} if "/images/" in path else {}
            target.create_dataset(
                name,
                shape=(0, *shape),
                maxshape=(None, *shape),
                chunks=(1, *shape),
                dtype=dtype,
                **options,
            )
        return group

    def _add_frame(self, request, raw):
        if request["recording_mode"] != self.mode:
            raise ValueError("Recording mode differs from dataset session")
        images = np.frombuffer(raw, dtype=np.uint8).reshape((len(IMAGE_KEYS), *self.shape))
        state = np.asarray(request["state"], dtype=np.float32)
        action = np.asarray(request["action"], dtype=np.float32)
        if (
            state.shape != (len(self.schema.observation_fields),)
            or action.shape != (len(self.schema.action_fields),)
            or not np.isfinite(state).all()
            or not np.isfinite(action).all()
        ):
            raise ValueError("Invalid state/action")
        sample = request["sample_metadata"]
        serialized = json.dumps(sample, ensure_ascii=False, allow_nan=False)
        group = (
            self.file["pending_episode"] if self.frames else self._create_pending(request["task"])
        )
        if self.frames and float(sample["timestamp"]) <= group["timestamp"][-1]:
            raise ValueError("Capture timestamps must increase")
        values = {
            "timestamp": sample["timestamp"],
            "observation/state": state,
            "action/value": action,
            "metadata/samples": serialized,
            **{f"observation/images/{key}": images[i] for i, key in enumerate(IMAGE_KEYS)},
        }
        for key, path in RAW_PATHS.items():
            value = sample.get("raw", {}).get(key)
            values[path] = value if value is not None else np.full(6, np.nan)
            values[f"valid/{key}"] = value is not None
        for path, value in values.items():
            dataset = group[path]
            dataset.resize(self.frames + 1, axis=0)
            dataset[self.frames] = value
        self.frames += 1

    def finalize_best_effort(self):
        if self.file is not None:
            self.file.close()
            self.file = None
