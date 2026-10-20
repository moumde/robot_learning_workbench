"""Read-only validators and a common report for finalized datasets."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from .schema import IMAGE_KEYS, recording_schema


@dataclass
class ValidationReport:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    episode_count: int = 0
    frame_count: int = 0


class DatasetValidator(Protocol):
    def validate(self, dataset_path: Path) -> ValidationReport: ...


class CheckedValidator:
    def validate(self, dataset_path: Path) -> ValidationReport:
        report = ValidationReport()
        try:
            self._validate(Path(dataset_path), report)
        except Exception as exc:
            report.valid = False
            report.errors.append(f"{type(exc).__name__}: {exc}")
        return report


class LeRobotV3Validator(CheckedValidator):
    def _validate(self, root, report):
        from .validate_dataset import validate_dataset

        result = validate_dataset(root)
        report.episode_count = result["episodes"]
        report.frame_count = result["frames"]
        if result["needs_review_episodes"]:
            report.warnings.append(f"Episodes need review: {result['needs_review_episodes']}")


class HDF5Validator(CheckedValidator):
    def _validate(self, root, report):
        import h5py

        with h5py.File(root / "dataset.hdf5", "r") as file:
            metadata = file["metadata"].attrs
            for key in (
                "dataset_id",
                "dataset_name",
                "task_name",
                "robot_type",
                "hand_type",
                "fps",
                "created_at",
                "schema_version",
                "schema_hash",
                "recording_mode",
                "format_version",
            ):
                if key not in metadata:
                    raise ValueError(f"Missing metadata: {key}")
            schema = recording_schema(metadata["recording_mode"])
            episodes = file["episodes"]
            if list(episodes) != [f"{i:06d}" for i in range(len(episodes))]:
                raise ValueError("Episode indices are not continuous")
            report.episode_count = len(episodes)
            if "pending_episode" in file:
                raise ValueError("Dataset contains an unfinished pending episode")
            for name, episode in episodes.items():
                times = episode["timestamp"][:]
                count = len(times)
                if not count or not np.isfinite(times).all() or (np.diff(times) <= 0).any():
                    raise ValueError(f"Episode {name}: invalid timestamps")
                for key, dim in (
                    ("observation/state", len(schema.observation_fields)),
                    ("action/value", len(schema.action_fields)),
                ):
                    values = episode[key][:]
                    if values.shape != (count, dim) or not np.isfinite(values).all():
                        raise ValueError(f"Episode {name}: invalid {key} shape/values")
                image_shape = tuple(json.loads(metadata["image_size"]))
                for key in IMAGE_KEYS:
                    image = episode[f"observation/images/{key}"]
                    if image.shape != (count, *image_shape, 3) or image.dtype != np.uint8:
                        raise ValueError(f"Episode {name}: invalid image {key}")

                def check_length(path, value, count=count, name=name):
                    if isinstance(value, h5py.Dataset) and value.shape[0] != count:
                        raise ValueError(f"Episode {name}: {path} length differs from timestamps")

                episode.visititems(check_length)
                attrs = episode["metadata"].attrs
                if attrs["frame_count"] != count or attrs["outcome"] not in ("success", "failure"):
                    raise ValueError(f"Episode {name}: invalid result metadata")
                if attrs["episode_index"] != int(name) or not attrs["task"].strip():
                    raise ValueError(f"Episode {name}: invalid index/task")
                report.frame_count += count


class LeRobotV21Validator(CheckedValidator):
    def _validate(self, root, report):
        import av
        import pyarrow.parquet as pq

        info = json.loads((root / "meta/info.json").read_text())
        if info["codebase_version"] != "v2.1":
            raise ValueError("Expected LeRobot V2.1 metadata")
        for name in ("stats.json", "episodes_stats.jsonl"):
            if not (root / "meta" / name).is_file():
                raise ValueError(f"Missing {name}")
        json.loads((root / "meta/stats.json").read_text())
        tasks = {row["task_index"]: row["task"] for row in _jsonlines(root / "meta/tasks.jsonl")}
        episodes = _jsonlines(root / "meta/episodes.jsonl")
        if [ep["episode_index"] for ep in episodes] != list(range(len(episodes))):
            raise ValueError("Episode indices are not continuous")
        manifest = json.loads((root / "meta/collection/session.json").read_text())
        schema = recording_schema(manifest["recording_mode"])
        for key, fields in (
            ("observation.state", schema.observation_fields),
            ("action", schema.action_fields),
        ):
            if info["features"][key]["shape"] != [len(fields)] or (
                info["features"][key]["names"] != list(fields)
            ):
                raise ValueError(f"{key}: incorrect feature mapping")
        fps = float(info["fps"])
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("Invalid FPS")
        for ep in episodes:
            index = ep["episode_index"]
            values = {"episode_index": index, "episode_chunk": index // info["chunks_size"]}
            rows = pq.read_table(root / info["data_path"].format(**values)).to_pylist()
            count = len(rows)
            if not count or count != ep["length"]:
                raise ValueError(f"Episode {index}: frame count mismatch")
            if (
                [r["frame_index"] for r in rows] != list(range(count))
                or any(r["episode_index"] != index for r in rows)
                or [r["index"] for r in rows]
                != list(range(report.frame_count, report.frame_count + count))
            ):
                raise ValueError(f"Episode {index}: invalid frame indices")
            for key, dim in (
                ("observation.state", len(schema.observation_fields)),
                ("action", len(schema.action_fields)),
            ):
                array = np.asarray([r[key] for r in rows])
                if array.shape != (count, dim) or not np.isfinite(array).all():
                    raise ValueError(f"Episode {index}: invalid {key}")
            times = np.asarray([r["timestamp"] for r in rows])
            if not np.allclose(times, np.arange(count) / fps, atol=1e-4, rtol=0):
                raise ValueError(f"Episode {index}: invalid timestamps")
            sidecar = json.loads((root / f"meta/collection/episode_{index:06d}.json").read_text())
            host_times = np.asarray([s["timestamp"] for s in sidecar["samples"]])
            if (
                len(host_times) != count
                or not np.isfinite(host_times).all()
                or (np.diff(host_times) <= 0).any()
            ):
                raise ValueError(f"Episode {index}: invalid capture timestamps")
            if sidecar["outcome"] not in ("success", "failure") or sidecar["frame_count"] != count:
                raise ValueError(f"Episode {index}: invalid result metadata")
            if any(tasks[r["task_index"]] != sidecar["task"] for r in rows):
                raise ValueError(f"Episode {index}: task mismatch")
            for key in IMAGE_KEYS:
                feature_key = f"observation.images.{key}"
                feature = info["features"][feature_key]
                if feature["dtype"] != "video":
                    raise ValueError(f"{feature_key}: expected video")
                video = root / info["video_path"].format(video_key=feature_key, **values)
                decoded = 0
                with av.open(str(video)) as container:
                    for frame in container.decode(video=0):
                        if list(frame.to_ndarray(format="rgb24").shape) != feature["shape"]:
                            raise ValueError(f"{video}: incorrect image shape")
                        if frame.time is None or abs(float(frame.time) - decoded / fps) > 1e-3:
                            raise ValueError(f"{video}: incorrect image timestamps")
                        decoded += 1
                if decoded != count:
                    raise ValueError(f"{video}: image/frame count mismatch")
            report.frame_count += count
        report.episode_count = len(episodes)
        if (info["total_episodes"], info["total_frames"]) != (
            report.episode_count,
            report.frame_count,
        ):
            raise ValueError("Dataset metadata counts differ from episode contents")


def _jsonlines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
