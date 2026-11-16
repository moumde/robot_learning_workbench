import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from teleop.gello_cr.recording.batch import BatchManager, recording_profile
from teleop.gello_cr.recording.errors import RecordingError
from teleop.gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.manifest import BatchStatus
from teleop.gello_cr.recording.schema import IMAGE_KEYS
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.recording.writers.factory import WriterFactory


def source_frame():
    ts = time.monotonic()
    quality = {"camera_skew_s": 0.0}
    for camera in ("base", "wrist", "roi"):
        quality.update({f"{camera}_timestamp": ts, f"{camera}_age_s": 0.0})
    return CaptureFrame(
        ts,
        (0.1,) * 12,
        (0.2,) * 12,
        {key: np.full((16, 16, 3), 90, np.uint8) for key in IMAGE_KEYS},
        robot_joint_state=(0.1,) * 6,
        metadata={"recording_mode": "joint", "quality": quality},
    )


def make_manager(tmp_path, profile=None):
    writer_factory = WriterFactory(
        DatasetWriterConfig(
            DatasetFormat.HDF5, worker_python=sys.executable, hdf5_compression="lzf"
        )
    )
    session = RecordingSession(
        SimpleNamespace(capture=source_frame),
        writer_factory,
        event_callback=lambda *a: None,
        image_size=(16, 16),
    )
    current = profile or recording_profile(mode="joint", fps=20, image_size=(16, 16))
    return BatchManager(
        session, staging_root=tmp_path / "staging", profile_provider=lambda: current
    )


def record_some(manager, tmp_path):
    manager.start_episode("pick motor", str(tmp_path / "train"))
    deadline = time.monotonic() + 3
    while manager.snapshot()["buffered_frames"] < 3:
        assert not manager.snapshot()["error"]
        assert time.monotonic() < deadline
        time.sleep(0.01)
    manager.stop_episode()


def test_resume_creates_a_new_segment_and_requires_a_partial_decision(tmp_path):
    h5py = pytest.importorskip("h5py")
    first = make_manager(tmp_path)
    record_some(first, tmp_path)
    first.save_episode("success")
    record_some(first, tmp_path)
    batch_id = first.snapshot()["batch_id"]
    assert first.recovery.scan() == []  # A live process owns the batch lock.
    first.suspend("test interruption")
    second = make_manager(tmp_path)
    recovered = second.recovery.scan()
    assert len(recovered) == 1 and recovered[0]["partial_episodes"][0]["episode_index"] == 1
    second.recovery.resume(batch_id)
    assert second.snapshot()["segment_id"] == "segment_001"
    assert second.snapshot()["next_episode_index"] == 2
    with pytest.raises(RecordingError, match="partial|Partial"):
        second.finalize()
    second.recovery.resolve_partial(batch_id, 1, "failure")
    root = Path(second.recovery.finalize(batch_id))
    with h5py.File(root / "dataset.hdf5", "r") as file:
        assert len(file["episodes"]) == 2
        assert file["episodes/000001/metadata"].attrs["outcome"] == "failure"
        quality = json.loads(file["episodes/000001/metadata"].attrs["quality"])
        assert quality["needs_review"]
    assert second.recovery.scan() == []
    manifest = json.loads((tmp_path / "staging" / batch_id / "manifest.json").read_text())
    assert manifest["status"] == BatchStatus.COMPLETED
    assert (tmp_path / "staging" / batch_id / "segment_000" / "dataset").exists()


@pytest.mark.parametrize("selected_format", [DatasetFormat.LEROBOT_V21, DatasetFormat.LEROBOT_V3])
def test_resume_adopts_hdf5_batch_format_without_starting_sampling(tmp_path, selected_format):
    h5py = pytest.importorskip("h5py")
    first = make_manager(tmp_path)
    record_some(first, tmp_path)
    first.save_episode("success")
    batch_id = first.snapshot()["batch_id"]
    first.suspend("test interruption")
    resumed = make_manager(tmp_path)
    resumed.writer_factory.select(selected_format)

    def unexpected_capture():
        raise AssertionError("Resume must not start camera sampling")

    resumed.session.source = SimpleNamespace(capture=unexpected_capture)
    try:
        resumed.recovery.resume(batch_id)
        snapshot = resumed.snapshot()
        assert snapshot["session_active"]
        assert not snapshot["episode_active"]
        assert not snapshot["episode_pending"]
        assert snapshot["buffered_frames"] == 0
        assert snapshot["format"] == "hdf5"
        assert resumed.writer_factory.format_name == "hdf5"
        assert resumed._segment_writer.writer.format_name == "hdf5"
        final = Path(resumed.finalize())
        with h5py.File(final / "dataset.hdf5", "r") as file:
            assert len(file["episodes"]) == 1
            assert file["episodes/000000/metadata"].attrs["outcome"] == "success"
    finally:
        resumed.close()


def test_resume_restores_selected_format_when_segment_open_fails(tmp_path, monkeypatch):
    first = make_manager(tmp_path)
    first.create_dataset("pick motor", tmp_path / "train")
    batch_id = first.snapshot()["batch_id"]
    first.suspend("test interruption")
    resumed = make_manager(tmp_path)
    resumed.writer_factory.select(DatasetFormat.LEROBOT_V3)
    selected_config = resumed.writer_factory.config

    def unavailable(writer, metadata):
        assert resumed.writer_factory.format_name == "hdf5"
        assert writer.format_name == "hdf5"
        raise OSError("recovery writer unavailable")

    monkeypatch.setattr(resumed.session, "open_writer", unavailable)
    with pytest.raises(OSError, match="recovery writer unavailable"):
        resumed.recovery.resume(batch_id)
    assert resumed.writer_factory.config == selected_config
    assert not resumed.snapshot()["session_active"]
    assert resumed.recovery.scan()[0]["batch_id"] == batch_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("fps", 10),
        ("recording_mode", "tcp"),
        ("robot_type", "cr5"),
        ("image_size", [224, 224]),
        ("camera_configuration", [{"serial": "other"}]),
        ("schema_hash", "different_schema"),
    ],
)
def test_resume_rejects_changed_capture_profile(tmp_path, field, value):
    manager = make_manager(tmp_path)
    manager.create_dataset("pick motor", tmp_path / "train")
    batch_id = manager.snapshot()["batch_id"]
    manager.suspend("test")
    profile = recording_profile(mode="joint", fps=20, image_size=(16, 16))
    profile[field] = value
    changed = make_manager(tmp_path, profile)
    changed.writer_factory.select(DatasetFormat.LEROBOT_V3)
    selected_config = changed.writer_factory.config
    with pytest.raises(RecordingError, match=field):
        changed.recovery.resume(batch_id)
    assert changed.writer_factory.config == selected_config
    assert not changed.snapshot()["session_active"]
    assert not (tmp_path / "staging" / batch_id / "segment_001").exists()


@pytest.mark.parametrize("after_rename", [False, True])
def test_publish_failure_retains_sources_and_can_be_retried(tmp_path, monkeypatch, after_rename):
    from teleop.gello_cr.recording import merge

    manager = make_manager(tmp_path)
    record_some(manager, tmp_path)
    manager.save_episode("success")
    batch_id = manager.snapshot()["batch_id"]
    publish = merge.atomic_publish

    def fail(temporary, final):
        if after_rename:
            publish(temporary, final)
        raise OSError("interrupted publication")

    monkeypatch.setattr(merge, "atomic_publish", fail)
    with pytest.raises(OSError, match="interrupted publication"):
        manager.finalize()
    outputs = list((tmp_path / "train").iterdir())
    assert len(outputs) == 1
    assert outputs[0].name.startswith(".tmp_") != after_rename
    assert (tmp_path / "staging" / batch_id / "segment_000" / "episodes").exists()
    manager.suspend("retry later")
    monkeypatch.setattr(merge, "atomic_publish", publish)
    recovered = make_manager(tmp_path)
    final = Path(recovered.recovery.finalize(batch_id))
    assert final.exists() and not final.name.startswith(".")
    assert len([p for p in final.parent.iterdir() if not p.name.startswith(".")]) == 1
    assert recovered.recovery.scan() == []


def test_episode_boundary_resume_and_explicit_global_index_mapping(tmp_path):
    manager = make_manager(tmp_path)
    for _ in range(2):
        record_some(manager, tmp_path)
        manager.save_episode("success")
    batch_id = manager.snapshot()["batch_id"]
    manager.suspend("between episodes")
    resumed = make_manager(tmp_path)
    resumed.recovery.resume(batch_id)
    assert resumed.snapshot()["next_episode_index"] == 2
    assert not resumed.snapshot()["partial_episodes"]
    record_some(resumed, tmp_path)
    assert resumed.snapshot()['episode_index'] == 2
    assert resumed.snapshot()['local_episode_index'] == 0
    resumed.save_episode("failure")
    receipt = resumed.snapshot()['last_saved']
    assert receipt['episode_index'] == 2
    assert receipt['local_episode_index'] == 0
    assert receipt['batch_id'] == batch_id
    assert receipt['segment_id'] == 'segment_001'
    assert Path(receipt['episode_path']).is_dir()
    assert Path(receipt['journal_path']).is_file()
    assert receipt['dataset_id'] == resumed.snapshot()['dataset_id']
    assert receipt['root'] == resumed.snapshot()['root']
    final = Path(resumed.finalize())
    mapping = json.loads((final / "batch_provenance.json").read_text())["episode_mapping"]
    assert [r["global_episode_index"] for r in mapping] == [0, 1, 2]
    assert [r["episode_index"] for r in mapping] == [0, 1, 2]
    assert mapping[-1]["local_episode_index"] == 0


def test_merge_rejects_incompatible_segment_without_publishing(tmp_path):
    from teleop.gello_cr.recording.manifest import SegmentManifest

    manager = make_manager(tmp_path)
    record_some(manager, tmp_path)
    manager.save_episode("success")
    batch_id = manager.snapshot()["batch_id"]
    manager.suspend()
    segment_root = tmp_path / "staging" / batch_id / "segment_000"
    segment = SegmentManifest.load(segment_root)
    segment.profile["fps"] = 10
    segment.save(segment_root)
    recovered = make_manager(tmp_path)
    with pytest.raises(RecordingError, match="fps mismatch"):
        recovered.recovery.finalize(batch_id)
    assert not list((tmp_path / "train").glob("*"))


def test_application_resume_does_not_start_sampling_or_robot_control(tmp_path):
    from teleop.gello_cr.app.runtime_bindings import RuntimeCommandBindings
    from teleop.gello_cr.app.service import ApplicationService
    from teleop.gello_cr.core.state_machine import Command, WorkflowState

    first = make_manager(tmp_path)
    record_some(first, tmp_path)
    first.save_episode("success")
    batch_id = first.snapshot()["batch_id"]
    first.suspend()
    second = make_manager(tmp_path)

    def capture():
        raise AssertionError("Resume must not start camera sampling")

    second.session.source = SimpleNamespace(capture=capture)
    app = ApplicationService()
    RuntimeCommandBindings(app, teleop_engine=SimpleNamespace(), recorder=second).install()
    app.dispatch(Command.RESUME_BATCH, {"batch_id": batch_id})
    assert app.state is WorkflowState.OFFLINE
    assert second.snapshot()["segment_id"] == "segment_001"
    assert not second.snapshot()["episode_active"]
    app.dispatch(Command.FINALIZE_BATCH, {"batch_id": batch_id})
    assert second.snapshot()["validation"]["valid"]
    assert app.state is WorkflowState.OFFLINE


def test_closing_an_empty_batch_does_not_publish_or_offer_recovery(tmp_path):
    manager = make_manager(tmp_path)
    manager.create_dataset("pick motor", tmp_path / "train")
    batch_id = manager.snapshot()["batch_id"]
    manager.close()
    assert not list((tmp_path / "train").glob("*"))
    assert manager.recovery.scan() == []
    manifest = json.loads((tmp_path / "staging" / batch_id / "manifest.json").read_text())
    assert manifest["status"] == "discarded"


def test_episode_begin_io_failure_remains_visible_as_unresolved_partial(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)

    def unavailable(*args, **kwargs):
        raise OSError("journal unavailable")

    monkeypatch.setattr("teleop.gello_cr.recording.segment.FrameJournal", unavailable)
    with pytest.raises(OSError, match="journal unavailable"):
        manager.start_episode("pick motor", tmp_path / "train")
    assert manager.snapshot()["partial_episodes"] == [{"episode_index": 0, "frame_count": 0}]
    batch_id = manager.snapshot()["batch_id"]
    manager.suspend("journal unavailable")
    manager.recovery.resolve_partial(batch_id, 0, "discard")
    assert manager.recovery.finalize(batch_id) is None


def test_task_name_and_instruction_survive_segment_merge(tmp_path):
    import h5py
    manager = make_manager(tmp_path)
    manager.create_dataset('motor_pick', tmp_path / 'train',
                           task_description='Pick up the motor and place it in the tray.')
    try:
        record_some(manager, tmp_path)
        manager.save_episode('success')
        root = Path(manager.finalize())
        assert root.name.startswith('motor_pick_')
        with h5py.File(root / 'dataset.hdf5', 'r') as file:
            assert file['metadata'].attrs['task_name'] == 'motor_pick'
            assert file['episodes/000000/metadata'].attrs['task'] == 'Pick up the motor and place it in the tray.'
    finally:
        manager.close()
