"""Kill the capture process and its SDK worker; rebuild only from durable journals."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_recovery import record_some, source_frame

from gello_cr.recording.batch import BatchManager, recording_profile
from gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from gello_cr.recording.session import RecordingSession
from gello_cr.recording.writers.factory import WriterFactory, create_validator

CAPTURE_PROCESS = """
import json, signal, sys, time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from gello_cr.recording.batch import BatchManager, recording_profile
from gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from gello_cr.recording.frame import CaptureFrame
from gello_cr.recording.manifest import atomic_json
from gello_cr.recording.schema import IMAGE_KEYS
from gello_cr.recording.session import RecordingSession
from gello_cr.recording.writers.factory import WriterFactory
root, format_name, python = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def frame():
    ts = time.monotonic()
    quality = {"camera_skew_s": 0.}
    for camera in ("base", "wrist", "roi"):
        quality.update({f"{camera}_timestamp": ts, f"{camera}_age_s": 0.})
    return CaptureFrame(ts, (.1,) * 12, (.2,) * 12,
        {key: np.full((224,224,3), 90, np.uint8) for key in IMAGE_KEYS},
        metadata={"recording_mode": "joint", "quality": quality})
factory = WriterFactory(DatasetWriterConfig(DatasetFormat(format_name), worker_python=python))
session = RecordingSession(SimpleNamespace(capture=frame), factory,
    event_callback=lambda *args: None, image_size=(224,224))
manager = BatchManager(session, staging_root=root / "staging",
    profile_provider=lambda: recording_profile(mode="joint", fps=20, image_size=(224,224)))
def record(count):
    manager.start_episode("pick motor", root / "train")
    while manager.snapshot()["buffered_frames"] < count:
        assert not manager.snapshot()["error"], manager.snapshot()["error"]
        time.sleep(.005)
record(3)
manager.stop_episode()
manager.save_episode("success")
record(100)
if len(sys.argv) > 4 and sys.argv[4] == "boundary":
    manager.stop_episode()
    manager.save_episode("failure")
atomic_json(root / "ready.json", {"batch_id": manager.snapshot()["batch_id"]})
signal.pause()
"""


@pytest.mark.parametrize(
    "format_name,decision",
    [
        ("lerobot_v21", "discard"),
        ("lerobot_v3", "failure"),
        ("hdf5", "failure"),
        ("hdf5", "boundary"),
    ],
)
def test_process_group_crash_resume_merge_real_formats(tmp_path, format_name, decision):
    python = {
        "lerobot_v21": os.environ.get("GELLO_TEST_V21_PYTHON"),
        "lerobot_v3": os.environ.get("GELLO_TEST_V3_PYTHON"),
        "hdf5": sys.executable,
    }[format_name]
    if not python:
        pytest.skip(f"Provide the external {format_name} SDK Python")
    script = tmp_path / "capture_process.py"
    script.write_text(CAPTURE_PROCESS)
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    with (tmp_path / "capture.stderr").open("w") as error:
        process = subprocess.Popen(
            [sys.executable, str(script), str(tmp_path), format_name, python, decision],
            stdout=subprocess.DEVNULL,
            stderr=error,
            env=env,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 40
            while not (tmp_path / "ready.json").exists():
                assert process.poll() is None, (tmp_path / "capture.stderr").read_text()
                assert time.monotonic() < deadline, (tmp_path / "capture.stderr").read_text()
                time.sleep(0.02)
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    batch_id = json.loads((tmp_path / "ready.json").read_text())["batch_id"]
    factory = WriterFactory(DatasetWriterConfig(DatasetFormat(format_name), worker_python=python))
    session = RecordingSession(
        SimpleNamespace(capture=source_frame),
        factory,
        event_callback=lambda *a: None,
        image_size=(224, 224),
    )
    manager = BatchManager(
        session,
        staging_root=tmp_path / "staging",
        profile_provider=lambda: recording_profile(mode="joint", fps=20, image_size=(224, 224)),
    )
    recovered = manager.recovery.scan()[0]
    assert recovered["episodes"] == (2 if decision == "boundary" else 1)
    if decision == "boundary":
        assert recovered["partial_episodes"] == []
    else:
        partial = recovered["partial_episodes"][0]
        assert partial["frame_count"] >= 100
    manager.recovery.resume(batch_id)
    assert manager.snapshot()["segment_id"] == "segment_001"
    assert manager.snapshot()["next_episode_index"] == 2
    if decision != "boundary":
        manager.recovery.resolve_partial(batch_id, 1, decision)
    record_some(manager, tmp_path)
    count = manager.snapshot()["buffered_frames"]
    manager.save_episode("failure")
    final = Path(manager.finalize())
    report = create_validator(format_name).validate(final)
    assert report.valid, report.errors
    assert report.episode_count == (2 if decision == "discard" else 3)
    assert report.frame_count == recovered["frames"] + count + (
        partial["frame_count"] if decision == "failure" else 0
    )
    provenance = json.loads((final / "batch_provenance.json").read_text())
    assert provenance["batch_id"] == batch_id
    assert provenance["episode_mapping"][-1]["global_episode_index"] == 2
    assert (tmp_path / "staging" / batch_id / "segment_000" / "dataset").is_dir()
    assert manager.recovery.scan() == []
