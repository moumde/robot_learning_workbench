"""Read-only validation of finalized LeRobot v3 recordings and collection evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from core.workbench.data_contract import ACTION_DIM, JOINT_STATE_FIELDS, recording_fields

from .writers.lerobot_v3_schema import LEGACY_SAMPLE_IMAGE_KEYS as SAMPLE_IMAGE_KEYS
from .writers.lerobot_v3_schema import LEROBOT_IMAGE_FEATURE_KEYS


def validate_dataset(root: str | Path) -> dict:
    # Optional data-environment dependencies; never import a hardware SDK.
    import av
    import pyarrow.parquet as pq

    root = Path(root).expanduser().resolve()
    info = json.loads((root / "meta/info.json").read_text())
    if not str(info["codebase_version"]).startswith("v3."):
        raise ValueError("Validator requires LeRobot v3 metadata")
    mode = (
        "joint"
        if info["features"]["observation.state"].get("names") == list(JOINT_STATE_FIELDS)
        else "tcp"
    )
    state_fields, action_fields = recording_fields(mode)
    state_dim = len(state_fields)
    if mode == "joint" and info["features"]["action"]["names"] != list(action_fields):
        raise ValueError("Joint action names/units do not match contract")
    fps = float(info["fps"])
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("Invalid fps")
    for key, dim in [("observation.state", state_dim), ("action", ACTION_DIM)]:
        if info["features"][key]["shape"] != [dim]:
            raise ValueError(f"{key}: invalid metadata dimension")
    data_files = sorted((root / "data").rglob("*.parquet"))
    episode_files = sorted((root / "meta/episodes").rglob("*.parquet"))
    if not data_files or not episode_files:
        raise ValueError("Missing finalized data/episode parquet files")
    rows = [row for path in data_files for row in pq.read_table(path).to_pylist()]
    episodes = [row for path in episode_files for row in pq.read_table(path).to_pylist()]
    tasks = pq.read_table(root / "meta/tasks.parquet").to_pandas()
    task_names = {int(row["task_index"]): str(name) for name, row in tasks.iterrows()}
    if not task_names or any(not name.strip() for name in task_names.values()):
        raise ValueError("Missing task text")
    if len(rows) != info["total_frames"] or len(episodes) != info["total_episodes"]:
        raise ValueError("Metadata frame/episode count mismatch")
    if [int(r["index"]) for r in rows] != list(range(len(rows))):
        raise ValueError("Global frame indices are missing/duplicated/unordered")
    episode_ids = [int(ep["episode_index"]) for ep in episodes]
    if sorted(episode_ids) != list(range(len(episodes))):
        raise ValueError("Episode indices are missing/duplicated")
    if {int(r["episode_index"]) for r in rows} != set(episode_ids):
        raise ValueError("Frame episode references do not match metadata")

    expected_sidecars = {root / f"meta/collection/episode_{i:06d}.json" for i in episode_ids}
    if set((root / "meta/collection").glob("episode_*.json")) != expected_sidecars:
        raise ValueError("Unreferenced/missing collection sidecars")
    decoded: dict[Path, np.ndarray] = {}
    video_expected: dict[Path, int] = {}
    review = []
    for ep in episodes:
        index = int(ep["episode_index"])
        frames = [r for r in rows if int(r["episode_index"]) == index]
        count = len(frames)
        if count != int(ep["length"]) or count == 0:
            raise ValueError(f"Episode {index}: frame count mismatch")
        if [int(r["frame_index"]) for r in frames] != list(range(count)):
            raise ValueError(f"Episode {index}: invalid frame indices")
        for key, dim in [("observation.state", state_dim), ("action", ACTION_DIM)]:
            array = np.asarray([r[key] for r in frames], dtype=float)
            if array.shape != (count, dim) or not np.isfinite(array).all():
                raise ValueError(f"Episode {index}: {key} invalid shape or NaN/Inf")
        timestamps = np.asarray([r["timestamp"] for r in frames], dtype=float)
        if not np.isfinite(timestamps).all() or not np.allclose(
            timestamps, np.arange(count) / fps, atol=1e-4, rtol=0
        ):
            raise ValueError(f"Episode {index}: invalid dataset timestamps")
        sidecar = json.loads((root / f"meta/collection/episode_{index:06d}.json").read_text())
        if sidecar.get("recording_mode", "tcp") != mode:
            raise ValueError("Episode recording mode mismatch")
        if sidecar["episode_index"] != index or sidecar["frame_count"] != count:
            raise ValueError(f"Episode {index}: collection count mismatch")
        if sidecar["outcome"] not in ("success", "failure"):
            raise ValueError(f"Episode {index}: invalid outcome")
        if not isinstance(sidecar["context"], dict) or not isinstance(sidecar["quality"], dict):
            raise ValueError(f"Episode {index}: missing context/quality metadata")
        json.dumps(sidecar, allow_nan=False)
        if any(task_names[int(r["task_index"])] != sidecar["task"] for r in frames):
            raise ValueError(f"Episode {index}: task mismatch")
        streams = sidecar.get("camera_streams")
        if streams:
            from core.hardware.camera_streams import resolve_camera_streams

            resolve_camera_streams(
                {
                    "camera_streams": [
                        {key: stream[key] for key in ("name", "serial", "mode", "roi_norm")}
                        for stream in streams
                    ]
                }
            )
            if [stream["feature_key"] for stream in streams] != list(
                LEROBOT_IMAGE_FEATURE_KEYS
            ) or [stream["sample_key"] for stream in streams] != list(SAMPLE_IMAGE_KEYS):
                raise ValueError(f"Episode {index}: camera slot order mismatch")
            image_streams = {stream["name"]: stream["feature_key"] for stream in streams}
        else:
            image_streams = dict(
                zip(("Base RGB", "Wrist RGB", "Base ROI"), LEROBOT_IMAGE_FEATURE_KEYS, strict=True)
            )
        if sidecar["image_streams"] != image_streams:
            raise ValueError(f"Episode {index}: image stream mapping mismatch")
        samples = sidecar["samples"]
        if len(samples) != count:
            raise ValueError(f"Episode {index}: sample/image count mismatch")
        host_ts = np.asarray([s["timestamp"] for s in samples], dtype=float)
        if not np.isfinite(host_ts).all() or (np.diff(host_ts) <= 0).any():
            raise ValueError(f"Episode {index}: invalid host timestamps")
        for sample in samples:
            quality = sample["quality"]
            cameras = (
                ("wrist", "base", "roi")
                if streams or "roi_timestamp" in quality
                else ("wrist", "base")
            )
            for key in [
                *(f"{camera}_{suffix}" for camera in cameras for suffix in ("timestamp", "age_s")),
                "camera_skew_s",
            ]:
                value = float(quality[key])
                if not np.isfinite(value) or value < 0:
                    raise ValueError(f"Episode {index}: invalid {key}")
            camera_times = [quality[f"{camera}_timestamp"] for camera in cameras]
            if not np.isclose(
                quality["camera_skew_s"], max(camera_times) - min(camera_times), atol=1e-6
            ):
                raise ValueError(f"Episode {index}: camera skew inconsistent")
            for camera in cameras:
                if not np.isclose(
                    quality[f"{camera}_age_s"] - quality["base_age_s"],
                    quality["base_timestamp"] - quality[f"{camera}_timestamp"],
                    atol=1e-6,
                ):
                    raise ValueError(f"Episode {index}: camera age inconsistent")
        if sidecar["quality"]["needs_review"]:
            review.append(index)
        for key in LEROBOT_IMAGE_FEATURE_KEYS:
            feature = info["features"][key]
            if feature["dtype"] != "video":
                raise ValueError(f"{key}: expected RGB video")
            path = root / info["video_path"].format(
                video_key=key,
                chunk_index=int(ep[f"videos/{key}/chunk_index"]),
                file_index=int(ep[f"videos/{key}/file_index"]),
            )
            start = float(ep[f"videos/{key}/from_timestamp"])
            end = float(ep[f"videos/{key}/to_timestamp"])
            if not np.isfinite([start, end]).all() or start < 0 or end <= start:
                raise ValueError(f"{path}: invalid episode video interval")
            if path not in decoded:
                pts = []
                with av.open(str(path)) as container:
                    for frame in container.decode(video=0):
                        rgb = frame.to_ndarray(format="rgb24")
                        if list(rgb.shape) != feature["shape"]:
                            raise ValueError(f"{path}: decoded image dimension mismatch")
                        pts.append(float(frame.time))
                decoded[path] = np.asarray(pts)
                if not pts or not np.isfinite(pts).all() or (np.diff(pts) <= 0).any():
                    raise ValueError(f"{path}: unreadable or unordered video timestamps")
            pts = decoded[path]
            selected = pts[(pts >= start - 1e-5) & (pts < end - 1e-5)]
            if len(selected) != count or not np.allclose(
                selected - start, timestamps, atol=1e-3, rtol=0
            ):
                raise ValueError(f"{path}: video frame count/timestamp mismatch")
            video_expected[path] = video_expected.get(path, 0) + count
    for path, expected in video_expected.items():
        if len(decoded[path]) != expected:
            raise ValueError(f"{path}: unreferenced or missing video frames")
    if set((root / "videos").rglob("*.mp4")) != set(decoded):
        raise ValueError("Unreferenced/missing video files")
    return {
        "root": str(root),
        "episodes": len(episodes),
        "frames": len(rows),
        "videos": len(decoded),
        "needs_review_episodes": review,
        "valid": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Finalized local LeRobot V2.1/V3 or HDF5 dataset")
    args = parser.parse_args()
    from dataclasses import asdict

    from .writers.factory import create_validator, detect_format

    root = Path(args.root).expanduser().resolve()
    report = create_validator(detect_format(root)).validate(root)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    if not report.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
