from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from gello_cr.recording.errors import WriterStateError
from gello_cr.recording.frame import CaptureFrame
from gello_cr.recording.metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
)
from gello_cr.recording.schema import IMAGE_KEYS
from gello_cr.recording.writers.lerobot_v3 import LeRobotV3Writer, dataset_features


class Client:
    def __init__(self):
        self.requests = []
        self.closed = False

    def request(self, payload, raw=b"", timeout=30.0):
        self.requests.append((payload, raw))
        return {"root": payload.get("root", ""), "episodes": 1}

    def close(self):
        self.closed = True


def test_v3_writer_keeps_existing_payload_features_and_worker_lifecycle(tmp_path):
    client = Client()
    writer = LeRobotV3Writer("/fake/python", "local/test", client_factory=lambda *a, **kw: client)
    frame = CaptureFrame(
        10.0,
        (0.0,) * 18,
        (1.0,) * 12,
        {key: np.full((2, 2, 3), i, dtype=np.uint8) for i, key in enumerate(IMAGE_KEYS)},
        metadata={"quality": {"base_age_s": 0.01}},
    )
    session = DatasetSessionMetadata(
        str(uuid4()),
        "pick",
        "cr3a",
        "o6",
        20.0,
        (2, 2),
        "tcp",
        datetime.now(UTC).isoformat(),
        tmp_path / "capture",
        "pick_lerobot_v3",
    )
    with pytest.raises(WriterStateError):
        writer.add_frame(frame)
    writer.open(session)
    with pytest.raises(WriterStateError):
        writer.add_frame(frame)
    writer.begin_episode(EpisodeMetadata("pick", 0, 9.0, {"operator": "test"}))
    writer.add_frame(frame)
    writer.save_episode(EpisodeResult(EpisodeOutcome.SUCCESS, "done", 11.0, 1, {"frames": 1}))
    writer.finalize()
    writer.close()

    assert [p["op"] for p, _ in client.requests] == [
        "init",
        "add_frame",
        "save_episode",
        "finalize",
    ]
    init, _ = client.requests[0]
    assert init["fps"] == 20 and init["height"] == init["width"] == 2
    assert init["repo_id"].startswith("local/test_")
    payload, raw = client.requests[1]
    assert payload["state"] == [0.0] * 18 and payload["action"] == [1.0] * 12
    assert payload["task"] == "pick"
    assert raw == b"".join(bytes([i]) * 12 for i in range(3))
    collection = client.requests[2][0]["collection"]
    assert collection["context"] == {"operator": "test"}
    assert collection["outcome"] == "success"
    assert collection["dataset_id"] == session.dataset_id
    assert dataset_features(2, 2)["observation.images.base_0_rgb"]["shape"] == (2, 2, 3)
    assert client.closed
    with pytest.raises(WriterStateError):
        writer.begin_episode(EpisodeMetadata("pick", 1, 12.0))
