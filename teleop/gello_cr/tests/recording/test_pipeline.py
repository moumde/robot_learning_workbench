"""Canonical capture through the real session, V3 mapper, and worker service."""

import json
import threading
import time

import numpy as np
import pytest

from teleop.gello_cr.app.config_store import TeleopConfigStore
from teleop.gello_cr.app.runtime import TeleopRuntime
from teleop.gello_cr.motion import JointTarget, MotionSource
from teleop.gello_cr.recording.errors import UnsupportedDatasetFormat
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.recording.source import CR3O6CaptureSource
from teleop.gello_cr.recording.writers.factory import create_writer
from teleop.gello_cr.recording.writers.lerobot_v3 import LeRobotV3Writer
from teleop.gello_cr.recording.writers.lerobot_v3_worker import LeRobotV3WorkerService
from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot


class Dataset:
    def __init__(self, **kwargs):
        self.root = kwargs["root"]
        self.config = kwargs
        self.pending = []
        self.episodes = []
        self.finalized = False

    def add_frame(self, frame):
        self.pending.append(frame)

    def save_episode(self):
        self.episodes.append(self.pending)
        self.pending = []

    def clear_episode_buffer(self):
        self.pending = []

    def finalize(self):
        self.finalized = True


class Client:
    def __init__(self, service):
        self.service = service
        self.two_frames = threading.Event()

    def request(self, payload, raw=b"", timeout=30.0):
        response, _ = self.service.handle_request(payload, raw)
        if self.service.buffered_frames >= 2:
            self.two_frames.set()
        return response

    def close(self):
        pass


@pytest.mark.parametrize("mode,dimension", [("tcp", 18), ("joint", 12)])
def test_capture_session_writer_worker_preserve_v3_training_contract(tmp_path, mode, dimension):
    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["dataset"]["recording_mode"] = mode
    store.data["trajectory"]["root"] = str(tmp_path / "trajectories")
    engine = TeleopRuntime(store, FakeRoArm(), FakeO6())
    engine.attach_robot(FakeRobot())
    lease = engine.motion.acquire(MotionSource.POLICY)
    lease.servo_joint(JointTarget((0.01,) * 6, time.monotonic()))
    engine.robot.joints = [0.2] * 6 + [0.0]
    engine.o6.set_target([200] * 6)
    source = CR3O6CaptureSource(engine.dataset_sample, store.data["dataset"])
    for index in range(3):
        source.update_stream(index, np.full((2, 2, 3), index, dtype=np.uint8), time.monotonic())
    captured = source.capture()
    assert captured.robot_joint_command == pytest.approx((0.01,) * 6)
    assert captured.robot_joint_state != captured.robot_joint_command
    assert captured.hand_command == (200,) * 6
    assert captured.metadata["motion_source"] == "POLICY"
    service = LeRobotV3WorkerService(Dataset, lambda **kwargs: kwargs)
    client = Client(service)
    writer = LeRobotV3Writer(
        "/unused/python", "local/regression", client_factory=lambda *a, **kw: client
    )
    session = RecordingSession(
        source, lambda: writer, event_callback=lambda *a: None, image_size=(2, 2)
    )
    counts = []
    try:
        for outcome in ("success", "failure", "discard"):
            client.two_frames.clear()
            session.start_episode("pick motor", str(tmp_path))
            assert client.two_frames.wait(2)
            session.stop_episode()
            count = session.snapshot()["buffered_frames"]
            if outcome == "discard":
                session.discard_episode()
            else:
                session.save_episode(outcome)
                counts.append(count)
        session.finalize()
        dataset = service.dataset
        assert dataset.config["fps"] == 20
        assert dataset.config["rgb_encoder"] == {
            "vcodec": "h264",
            "pix_fmt": "yuv420p",
            "crf": 18,
            "preset": "fast",
            "g": 20,
        }
        assert [len(episode) for episode in dataset.episodes] == counts
        row = dataset.episodes[0][0]
        assert row["observation.state"].shape == (dimension,)
        assert row["action"].shape == (12,)
        assert row["task"] == "pick motor"
        for key in captured.images:
            assert row[f"observation.images.{key}"].shape == (2, 2, 3)
        manifest = json.loads((dataset.root / "meta/collection/session.json").read_text())
        assert manifest["dataset_id"] == session.snapshot()["dataset_id"]
        collection = json.loads((dataset.root / "meta/collection/episode_000001.json").read_text())
        assert collection["outcome"] == "failure"
        assert collection["frame_count"] == counts[1]
        assert len(collection["samples"]) == counts[1]
        assert collection["samples"][0]["raw"]["robot_joint_command"] == [0.01] * 6
        assert dataset.finalized
    finally:
        engine.shutdown(close_devices=False)


def test_writer_factory_rejects_unimplemented_formats():
    with pytest.raises(UnsupportedDatasetFormat):
        create_writer("unsupported")
