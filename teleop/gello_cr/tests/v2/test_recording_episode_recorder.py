from types import SimpleNamespace

import pytest

from gello_cr.recording.errors import RecordingError
from gello_cr.recording.session import RecordingSession
from gello_cr.recording.writers.lerobot_v3 import LeRobotV3Writer
from test_recording_frame import _sample


class FakeWriter:
    format_name = "fake"

    def __init__(self):
        self.calls = []

    def open(self, metadata):
        self.calls.append("open")

    def begin_episode(self, metadata):
        self.calls.append("begin")

    def add_frame(self, frame):
        self.calls.append("add")

    def save_episode(self, metadata):
        self.calls.append("save")

    def discard_episode(self):
        self.calls.append("discard")

    def finalize(self):
        self.calls.append("finalize")

    def close(self):
        self.calls.append("close")


def _recorder(**kwargs):
    return RecordingSession(
        SimpleNamespace(capture=_sample),
        lambda: FakeWriter(),
        event_callback=lambda *a: None,
        **kwargs,
    )


def test_constructor_preserves_recording_defaults():
    recorder = _recorder()
    assert recorder.fps == 20 and recorder.image_size == (224, 224)


def test_default_worker_script_is_packaged_with_writer():
    writer = LeRobotV3Writer("/fake/python", "local/test")
    assert writer.worker_script.name == "worker.py" and writer.worker_script.is_file()


def test_explicit_worker_script_is_supported(tmp_path):
    script = tmp_path / "worker.py"
    script.write_text("pass\n")
    writer = LeRobotV3Writer("/fake/python", "local/test", worker_script=script)
    assert writer.worker_script == script.resolve()


def test_initial_snapshot_preserves_quality_contract():
    snapshot = _recorder().snapshot()
    assert not snapshot["session_active"] and not snapshot["episode_active"]
    assert snapshot["buffered_frames"] == snapshot["saved_episodes"] == 0
    assert snapshot["quality"]["configured_fps"] == 20
    assert snapshot["quality"]["timestamp_basis"] == "host_monotonic_receipt_not_hardware_sync"


def test_start_episode_rejects_empty_task_before_writer_use():
    with pytest.raises(ValueError, match="task text cannot be empty"):
        _recorder().start_episode("  ", "/tmp/data")


def test_add_frame_updates_quality_after_writer_acknowledges():
    recorder = _recorder()
    writer = FakeWriter()
    recorder._writer = writer
    recorder._add_frame(_sample())
    assert recorder.snapshot()["buffered_frames"] == 1
    assert writer.calls == ["add"]


def test_finalize_preserves_writer_finalize_and_close_behavior():
    recorder = _recorder()
    writer = FakeWriter()
    recorder._writer = writer
    recorder._session_root = "/tmp/session"
    assert recorder.finalize() == "/tmp/session"
    assert writer.calls == ["finalize", "close"]
    assert recorder._writer is None


def test_preserve_failed_session_requires_existing_error():
    with pytest.raises(RecordingError, match="会话没有错误"):
        _recorder().preserve_failed_session()
