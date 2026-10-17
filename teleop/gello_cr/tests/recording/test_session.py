import threading
import time

import numpy as np
import pytest

from gello_cr.recording.frame import CaptureFrame
from gello_cr.recording.metadata import EpisodeOutcome
from gello_cr.recording.schema import IMAGE_KEYS
from gello_cr.recording.session import RecordingSession


class Source:
    def capture(self):
        return CaptureFrame(
            time.monotonic(),
            (0.0,) * 12,
            (1.0,) * 12,
            {k: np.zeros((2, 2, 3), dtype=np.uint8) for k in IMAGE_KEYS},
            metadata={"recording_mode": "joint", "quality": {"tracking_error_exceeded": 1.0}},
        )


class Writer:
    format_name = "test_format"

    def __init__(self):
        self.calls = []
        self.frame_added = threading.Event()

    def open(self, metadata):
        self.calls.append(("open", metadata))

    def begin_episode(self, metadata):
        self.calls.append(("begin", metadata))

    def add_frame(self, frame):
        self.calls.append(("add", frame))
        self.frame_added.set()

    def save_episode(self, result):
        self.calls.append(("save", result))

    def discard_episode(self):
        self.calls.append(("discard",))

    def finalize(self):
        self.calls.append(("finalize",))

    def close(self):
        self.calls.append(("close",))


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_session_drives_generic_writer_and_preserves_pending_lifecycle(tmp_path, outcome):
    writer = Writer()
    session = RecordingSession(
        Source(), lambda: writer, event_callback=lambda *a: None, fps=20, image_size=(2, 2)
    )
    assert not session.snapshot()["quality"]["needs_review"]
    session.start_episode("pick", str(tmp_path), metadata={"operator": "test"})
    assert writer.frame_added.wait(1)
    assert session.snapshot()["quality"]["needs_review"]
    session.stop_episode()
    assert session.snapshot()["buffered_frames"] > 0
    assert not session.snapshot()["episode_active"]
    assert session.snapshot()["quality"]["needs_review"]
    with pytest.raises(RuntimeError, match="未处理"):
        session.finalize()
    session.save_episode(outcome, "review")
    assert not session.snapshot()["quality"]["needs_review"]
    writer.frame_added.clear()
    session.start_episode("pick", str(tmp_path))
    assert writer.frame_added.wait(1)
    session.discard_episode()
    session.finalize()
    names = [call[0] for call in writer.calls]
    assert names[:2] == ["open", "begin"]
    assert names[-3:] == ["discard", "finalize", "close"]
    assert names.count("open") == 1
    result = next(call[1] for call in writer.calls if call[0] == "save")
    assert result.outcome is EpisodeOutcome(outcome)
    assert result.quality["needs_review"]
    metadata = writer.calls[0][1]
    assert metadata.recording_mode == "joint"
    assert metadata.display_name.endswith("_test_format")
    assert metadata.root.parent == tmp_path
