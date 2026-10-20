from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from teleop.gello_cr.recording.writers.lerobot_v3_worker import LeRobotV3WorkerService


class FakeDataset:
    def __init__(self, root: Path):
        self.root = root
        self.frames = []
        self.save_calls = 0
        self.clear_calls = 0
        self.finalize_calls = 0

    def add_frame(self, frame):
        self.frames.append(frame)

    def save_episode(self):
        self.save_calls += 1

    def clear_episode_buffer(self):
        self.clear_calls += 1

    def finalize(self):
        self.finalize_calls += 1


class Factory:
    def __init__(self):
        self.calls = []
        self.dataset = None

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        self.dataset = FakeDataset(Path(kwargs["root"]))
        return self.dataset


class EncoderFactory:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return {"encoder": kwargs}


def _service():
    dataset_factory = Factory()
    encoder_factory = EncoderFactory()
    service = LeRobotV3WorkerService(
        dataset_factory=dataset_factory,
        encoder_factory=encoder_factory,
    )
    return service, dataset_factory, encoder_factory


def _init(service, tmp_path):
    return service.handle_request(
        {
            "op": "init",
            "repo_id": "ace/test",
            "root": str(tmp_path / "dataset"),
            "fps": 20,
            "height": 224,
            "width": 224,
        },
        b"",
    )


def _raw_frame():
    return bytes(3 * 224 * 224 * 3)


def test_init_preserves_dataset_and_encoder_configuration(tmp_path) -> None:
    service, dataset_factory, encoder_factory = _service()

    response, should_exit = _init(service, tmp_path)

    assert response == {
        "ok": True,
        "root": str((tmp_path / "dataset").resolve()),
    }
    assert not should_exit

    call = dataset_factory.calls[0]
    assert call["repo_id"] == "ace/test"
    assert call["fps"] == 20
    assert call["robot_type"] == "dobot_cr5_o6"
    assert call["use_videos"] is True
    assert call["streaming_encoding"] is True
    assert call["encoder_queue_maxsize"] == 10
    assert call["encoder_threads"] == 2
    assert call["batch_encoding_size"] == 1

    assert encoder_factory.calls == [
        {
            "vcodec": "h264",
            "pix_fmt": "yuv420p",
            "crf": 18,
            "preset": "fast",
            "g": 20,
        }
    ]


def test_init_rejects_odd_image_size(tmp_path) -> None:
    service, _, _ = _service()

    with pytest.raises(ValueError, match="even"):
        service.handle_request(
            {
                "op": "init",
                "repo_id": "ace/test",
                "root": str(tmp_path / "dataset"),
                "fps": 20,
                "height": 224,
                "width": 201,
            },
            b"",
        )


def test_add_frame_preserves_three_stream_order_and_shapes(tmp_path) -> None:
    service, factory, _ = _service()
    _init(service, tmp_path)

    one_image = 224 * 224 * 3
    raw = (
        bytes([1]) * one_image
        + bytes([2]) * one_image
        + bytes([3]) * one_image
    )
    response, should_exit = service.handle_request(
        {
            "op": "add_frame",
            "state": [0.0] * 18,
            "action": [0.0] * 12,
            "task": "task",
        },
        raw,
    )

    assert response == {"ok": True, "frames": 1}
    assert not should_exit
    frame = factory.dataset.frames[0]
    assert np.all(frame["observation.images.base_0_rgb"] == 1)
    assert np.all(frame["observation.images.left_wrist_0_rgb"] == 2)
    assert np.all(frame["observation.images.right_wrist_0_rgb"] == 3)
    assert frame["observation.state"].shape == (18,)
    assert frame["action"].shape == (12,)
    assert frame["task"] == "task"


def test_add_frame_rejects_wrong_raw_size(tmp_path) -> None:
    service, _, _ = _service()
    _init(service, tmp_path)

    with pytest.raises(ValueError, match="3-stream RGB payload"):
        service.handle_request(
            {
                "op": "add_frame",
                "state": [0.0] * 18,
                "action": [0.0] * 12,
                "task": "task",
            },
            b"short",
        )


def test_add_frame_rejects_wrong_state_action_shape(tmp_path) -> None:
    service, _, _ = _service()
    _init(service, tmp_path)

    with pytest.raises(ValueError, match="Invalid state/action shapes"):
        service.handle_request(
            {
                "op": "add_frame",
                "state": [0.0] * 17,
                "action": [0.0] * 12,
                "task": "task",
            },
            _raw_frame(),
        )


def test_save_episode_writes_collection_sidecar_and_resets_buffer(tmp_path) -> None:
    service, factory, _ = _service()
    _init(service, tmp_path)
    service.handle_request(
        {
            "op": "add_frame",
            "state": [0.0] * 18,
            "action": [0.0] * 12,
            "task": "task",
        },
        _raw_frame(),
    )

    response, should_exit = service.handle_request(
        {
            "op": "save_episode",
            "collection": {
                "outcome": "success",
                "notes": "ok",
            },
        },
        b"",
    )

    assert response == {"ok": True, "episodes": 1}
    assert not should_exit
    assert service.buffered_frames == 0
    assert factory.dataset.save_calls == 1

    sidecar = (
        factory.dataset.root
        / "meta"
        / "collection"
        / "episode_000000.json"
    )
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["outcome"] == "success"
    assert saved["notes"] == "ok"
    assert saved["episode_index"] == 0


def test_clear_episode_preserves_legacy_buffer_behavior(tmp_path) -> None:
    service, factory, _ = _service()
    _init(service, tmp_path)
    service.buffered_frames = 3

    response, should_exit = service.handle_request(
        {"op": "clear_episode"},
        b"",
    )

    assert response == {"ok": True}
    assert not should_exit
    assert service.buffered_frames == 0
    assert factory.dataset.clear_calls == 1


def test_finalize_rejects_unsaved_frames(tmp_path) -> None:
    service, _, _ = _service()
    _init(service, tmp_path)
    service.buffered_frames = 1

    with pytest.raises(RuntimeError, match="Unsaved Episode"):
        service.handle_request({"op": "finalize"}, b"")


def test_finalize_marks_worker_exit_and_calls_dataset_finalize(tmp_path) -> None:
    service, factory, _ = _service()
    _init(service, tmp_path)

    response, should_exit = service.handle_request(
        {"op": "finalize"},
        b"",
    )

    assert response == {"ok": True, "episodes": 0}
    assert should_exit
    assert factory.dataset.finalize_calls == 1


def test_unknown_operation_is_rejected() -> None:
    service, _, _ = _service()

    with pytest.raises(ValueError, match="Unknown worker operation"):
        service.handle_request({"op": "nope"}, b"")


def test_joint_session_rejects_tcp_frames_and_records_joint_units(tmp_path):
    service, factory, _ = _service()
    service.handle_request({"op": "init", "repo_id": "local/joint", "root": str(tmp_path / "joint"),
                            "fps": 20, "height": 224, "width": 224,
                            "recording_mode": "joint"}, b"")
    assert factory.calls[0]["robot_type"] == "dobot_cr3_o6"
    assert factory.calls[0]["features"]["observation.state"]["names"][:6] == [
        f"cr3.q{i}.rad" for i in range(1, 7)
    ]
    request = {"op": "add_frame", "state": [0.] * 12, "action": [1.] * 12,
               "task": "test", "recording_mode": "tcp"}
    with pytest.raises(ValueError, match="mode"):
        service.handle_request(request, _raw_frame())
    assert not factory.dataset.frames
    request["recording_mode"] = "joint"
    service.handle_request(request, _raw_frame())
    np.testing.assert_equal(factory.dataset.frames[0]["action"], [1.] * 12)
