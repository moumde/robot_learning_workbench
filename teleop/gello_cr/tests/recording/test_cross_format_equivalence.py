"""Real files and official readers; SDKs remain in separate Python environments."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from teleop.gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
)
from teleop.gello_cr.recording.schema import IMAGE_KEYS
from teleop.gello_cr.recording.writers.factory import create_validator, create_writer


def test_real_cross_format_capture_and_official_readers(tmp_path, monkeypatch):
    pythons = {
        DatasetFormat.LEROBOT_V21: os.environ.get("GELLO_TEST_V21_PYTHON"),
        DatasetFormat.LEROBOT_V3: os.environ.get("GELLO_TEST_V3_PYTHON"),
        DatasetFormat.HDF5: sys.executable,
    }
    if not all(pythons.values()):
        pytest.skip("Set GELLO_TEST_V21_PYTHON and GELLO_TEST_V3_PYTHON for real SDK comparison")
    import h5py
    import pyarrow.parquet as pq

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    frames = []
    for i in range(100):
        timestamp = 10 + i / 20
        quality = {"camera_skew_s": 0.0}
        for camera in ("base", "wrist", "roi"):
            quality.update({f"{camera}_timestamp": timestamp, f"{camera}_age_s": 0.0})
        frames.append(
            CaptureFrame(
                timestamp,
                tuple(i * 0.001 + j * 0.01 for j in range(12)),
                tuple(i * 0.002 + j * 0.01 for j in range(12)),
                {
                    key: np.full((224, 224, 3), (i + k * 40) % 256, np.uint8)
                    for k, key in enumerate(IMAGE_KEYS)
                },
                robot_joint_state=(i * 0.001,) * 6,
                hand_command=(100.0,) * 6,
                metadata={"recording_mode": "joint", "quality": quality},
            )
        )
    expected_state = np.asarray([f.observation_state for f in frames])
    expected_action = np.asarray([f.action for f in frames])
    expected_times = np.asarray([f.timestamp for f in frames])
    for format_name, python in pythons.items():
        root = tmp_path / format_name.value
        session = DatasetSessionMetadata(
            str(uuid4()),
            "pick motor / 抓取",
            "cr3a",
            "o6",
            20,
            (224, 224),
            "joint",
            datetime.now(UTC).isoformat(),
            root,
            root.name,
        )
        writer = create_writer(
            DatasetWriterConfig(
                format_name,
                worker_python=python,
                hdf5_compression="lzf",
            )
        )
        writer.open(session)
        try:
            for index, outcome in enumerate(("success", "failure", "discard")):
                writer.begin_episode(EpisodeMetadata(session.task_name, index, 10.0))
                episode_frames = frames if index == 0 else frames[:5]
                for frame in episode_frames:
                    writer.add_frame(frame)
                if outcome == "discard":
                    writer.discard_episode()
                else:
                    writer.save_episode(
                        EpisodeResult(
                            EpisodeOutcome(outcome),
                            "synthetic",
                            episode_frames[-1].timestamp,
                            len(episode_frames),
                            {"needs_review": False},
                        )
                    )
            metrics = writer.metrics
            writer.finalize()
            assert writer.validation_report["valid"], writer.validation_report
        finally:
            writer.close()
        report = create_validator(format_name).validate(root)
        assert report.valid, report.errors
        assert (report.episode_count, report.frame_count) == (2, 105)
        if format_name is DatasetFormat.HDF5:
            with h5py.File(root / "dataset.hdf5", "r") as file:
                episode = file["episodes/000000"]
                state, action, times = (
                    episode[k][:] for k in ("observation/state", "action/value", "timestamp")
                )
                assert episode["metadata"].attrs["task"] == session.task_name
                for key in IMAGE_KEYS:
                    np.testing.assert_array_equal(
                        episode[f"observation/images/{key}"][:],
                        np.stack([f.images[key] for f in frames]),
                    )
        else:
            rows = [
                r
                for path in sorted((root / "data").rglob("*.parquet"))
                for r in pq.read_table(path).to_pylist()
                if r["episode_index"] == 0
            ]
            state = np.asarray([r["observation.state"] for r in rows])
            action = np.asarray([r["action"] for r in rows])
            sidecar = json.loads((root / "meta/collection/episode_000000.json").read_text())
            times = np.asarray([s["timestamp"] for s in sidecar["samples"]])
            assert sidecar["task"] == session.task_name
            # Official LeRobot uses regular episode-relative timestamps; the
            # original CaptureFrame clock remains in collection sidecars.
            np.testing.assert_allclose(
                [r["timestamp"] for r in rows], np.arange(100) / 20, atol=1e-4
            )
            script = """
import json, sys
from lerobot.datasets.lerobot_dataset import LeRobotDataset
dataset = LeRobotDataset("local/check", root=sys.argv[1], video_backend="pyav")
assert len(dataset) == 105
for index in (0, 50, 99, 104):
    row = dataset[index]
    assert tuple(row["observation.state"].shape) == (12,)
    assert tuple(row["action"].shape) == (12,)
    for key in ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb"):
        assert tuple(row["observation.images." + key].shape) == (3, 224, 224)
print(json.dumps({"frames": len(dataset), "reader": "official"}))
"""
            result = subprocess.run(
                [python, "-c", script, str(root)], capture_output=True, text=True, timeout=90
            )
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout.splitlines()[-1])["frames"] == 105
            from teleop.gello_cr.trajectory.adapters import LeRobotTrajectoryAdapter

            trajectory = LeRobotTrajectoryAdapter.load(root, episode_index=0)
            assert len(trajectory.frames) == 100
            np.testing.assert_allclose(
                trajectory.frames[-1].robot_joint_command, expected_action[-1, :6], atol=1e-6,
            )
        np.testing.assert_allclose(state, expected_state, atol=1e-6)
        np.testing.assert_allclose(action, expected_action, atol=1e-6)
        np.testing.assert_allclose(times, expected_times)
        print(format_name.value, metrics)
