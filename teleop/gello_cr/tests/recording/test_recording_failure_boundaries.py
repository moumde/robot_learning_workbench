"""Regression coverage for durable capture and pending episode boundaries."""

import threading
import time
from dataclasses import replace
from pathlib import Path

import h5py
import pytest

from teleop.gello_cr.recording.errors import RecordingError
from teleop.gello_cr.recording.journal import FrameJournal, read_frames
from teleop.gello_cr.recording.session import RecordingSession
from teleop.gello_cr.tests.recording.test_recovery import make_manager, source_frame
from teleop.gello_cr.tests.recording.test_session import Source, Writer


@pytest.mark.parametrize('failure', ['stale', 'disconnect'])
def test_running_camera_loss_retains_pending_and_allows_only_failure_save(tmp_path, failure):
    import numpy as np

    from teleop.gello_cr.recording.source import CR3O6CaptureSource

    image = np.zeros((2, 2, 3), dtype=np.uint8)
    source = CR3O6CaptureSource(
        lambda: {'timestamp': time.monotonic(), 'observation_state': [0.] * 12,
                 'action': [0.] * 12, 'recording_mode': 'joint'},
        {'camera_max_age_s': 0.2, 'camera_max_skew_s': 0.1},
    )
    now = time.monotonic()
    source.update_base(image, image, now)
    source.update_wrist(image, now)
    writer = Writer()
    session = RecordingSession(source, lambda: writer, event_callback=lambda *a: None,
                               fps=100, image_size=(2, 2))
    try:
        session.start_episode('capture', tmp_path)
        assert writer.frame_added.wait(1)
        # Normal repeated images remain usable until the configured freshness limit.
        deadline = time.monotonic() + 0.1
        while session.snapshot()['buffered_frames'] < 2 and time.monotonic() < deadline:
            time.sleep(0.002)
        assert session.snapshot()['episode_active']
        assert session.snapshot()['buffered_frames'] >= 2
        if failure == 'disconnect':
            source.invalidate_streams('USB disconnected: wrist-123')
        session._episode_thread.join(timeout=1)
        snapshot = session.snapshot()
        assert not snapshot['episode_active']
        assert snapshot['episode_pending']
        assert snapshot['error']
        assert 'disconnected' in snapshot['error'] if failure == 'disconnect' else '过期' in snapshot['error']
        with pytest.raises(RecordingError, match='only as failure'):
            session.save_episode('success')
        session.save_episode('failure')
        assert session.snapshot()['last_saved']['outcome'] == 'failure'
    finally:
        if session.snapshot()['episode_pending'] or session.snapshot()['episode_active']:
            session.discard_episode()
        session.finalize()


def test_sampling_counts_skipped_slots_separately_from_late_and_reused_frames(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('teleop.gello_cr.recording.session.time.monotonic', lambda: clock[0])
    writer = Writer()
    original_add = writer.add_frame

    def slow_first_frame(frame):
        original_add(frame)
        if len(writer.calls) == 1:
            clock[0] += 0.18

    writer.add_frame = slow_first_frame
    first = replace(Source().capture(), metadata={'recording_mode': 'joint', 'quality': {
        'base_timestamp': 9.99, 'wrist_timestamp': 9.99, 'roi_timestamp': 9.99,
    }})
    session = RecordingSession(
        type('Samples', (), {'capture': lambda _: replace(first, timestamp=clock[0])})(),
        lambda: writer, event_callback=lambda *a: None, image_size=(2, 2),
    )
    session._writer = writer
    session._recording_mode = 'joint'

    class StopAfterTwoWaits:
        waits = 0
        def is_set(self):
            return self.waits >= 2
        def wait(self, timeout):
            self.waits += 1
            clock[0] += timeout

    session._episode_stop = StopAfterTwoWaits()
    session._record_loop(first)
    quality = session.snapshot()['quality']
    assert quality['frames'] == 2
    assert quality['effective_fps'] == pytest.approx(5.0)
    assert quality['late_frames'] == 1
    assert quality['reused_camera_frames'] == {'base': 1, 'wrist': 1, 'roi': 1}
    assert quality['skipped_samples'] == 3
    assert quality['dropped_frames'] is None


def test_sampling_uses_slot_when_previous_ack_finishes_on_its_deadline(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('teleop.gello_cr.recording.session.time.monotonic', lambda: clock[0])
    writer = Writer()
    original_add = writer.add_frame

    def slow_first_frame(frame):
        original_add(frame)
        if len(writer.calls) == 1:
            clock[0] += 0.75

    writer.add_frame = slow_first_frame
    session = RecordingSession(
        Source(), lambda: writer, event_callback=lambda *a: None, fps=4, image_size=(2, 2),
    )
    session._writer = writer
    session._recording_mode = 'joint'

    class StopAfterTwoFrames:
        def is_set(self):
            return len(writer.calls) >= 2

        def wait(self, timeout):
            clock[0] += timeout

    session._episode_stop = StopAfterTwoFrames()
    session._record_loop(Source().capture())
    assert [call[1].timestamp for call in writer.calls] == [10.0, 10.75]
    assert session.snapshot()['quality']['skipped_samples'] == 2


@pytest.mark.parametrize('operation', ['allocate', 'checkpoint'])
def test_batch_snapshot_does_not_wait_for_manifest_fsync(tmp_path, monkeypatch, operation):
    from teleop.gello_cr.recording.manifest import BatchManifest, SegmentManifest

    manager = make_manager(tmp_path)
    manager.create_dataset('capture', tmp_path / 'train')
    manager._stop_heartbeat()
    manifest_type = BatchManifest if operation == 'allocate' else SegmentManifest
    original_save = manifest_type.save
    entered, release, snapshot_ready = threading.Event(), threading.Event(), threading.Event()

    def blocked_save(manifest, root):
        entered.set()
        assert release.wait(3)
        return original_save(manifest, root)

    monkeypatch.setattr(manifest_type, 'save', blocked_save)
    action = manager._allocate_episode if operation == 'allocate' else manager._checkpoint
    io_thread = threading.Thread(target=action)
    read_thread = threading.Thread(target=lambda: (manager.snapshot(), snapshot_ready.set()))
    try:
        io_thread.start()
        assert entered.wait(1)
        read_thread.start()
        assert snapshot_ready.wait(0.3), 'snapshot waited for manifest persistence'
    finally:
        release.set()
        io_thread.join(3)
        read_thread.join(3)
        manager.close()


def test_configured_hd_frame_survives_journal_roundtrip(tmp_path):
    journal = FrameJournal(tmp_path / "frames.bin", task="HD", image_size=(1080, 1920), mode="joint")
    try:
        journal.append(source_frame())
    finally:
        journal.close()
    frames = list(read_frames(journal.path))
    assert len(frames) == 1
    assert all(image.shape == (1080, 1920, 3) for image in frames[0].images.values())
    assert frames[0].action == source_frame().action


def test_backend_rejected_frame_can_be_recovered_as_failure(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    manager.create_dataset("capture", tmp_path / "train")
    backend = manager._segment_writer.writer
    original_add = backend.add_frame
    attempts = 0

    def reject_second(frame):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("backend rejected the second frame")
        return original_add(frame)

    monkeypatch.setattr(backend, "add_frame", reject_second)
    manager.start_episode("capture", tmp_path / "train")
    manager.session._episode_thread.join(timeout=3)
    assert not manager.snapshot()["episode_active"]
    assert manager.snapshot()["buffered_frames"] == 1
    batch_id = manager.snapshot()["batch_id"]
    try:
        with pytest.raises(RecordingError, match="partial|recover|恢复"):
            manager.save_episode("failure")
    finally:
        manager.suspend("backend rejection")
    recovered = make_manager(tmp_path)
    entry = recovered.recovery.scan()[0]
    assert entry["episodes"] == 0
    assert entry["partial_episodes"] == [{"episode_index": 0, "frame_count": 2}]
    recovered.recovery.resolve_partial(batch_id, 0, "failure")
    final = Path(recovered.recovery.finalize(batch_id))
    with h5py.File(final / "dataset.hdf5", "r") as file:
        episode = file["episodes/000000"]
        assert episode["metadata"].attrs["outcome"] == "failure"
        assert len(episode["timestamp"]) == 2


def test_first_frame_failure_remains_pending_until_explicit_discard(tmp_path):
    writer = Writer()

    def reject(frame):
        raise RuntimeError("first frame rejected")

    writer.add_frame = reject
    session = RecordingSession(
        Source(), lambda: writer, event_callback=lambda *args: None, image_size=(2, 2)
    )
    session.start_episode("capture", tmp_path)
    session._episode_thread.join(timeout=1)
    assert session.snapshot()["buffered_frames"] == 0
    assert session.snapshot()["episode_pending"]
    with pytest.raises(RecordingError, match="previous|未处理"):
        session.start_episode("capture", tmp_path)
    with pytest.raises(RecordingError, match="未处理"):
        session.finalize()
    session.discard_episode()
    assert not session.snapshot()["episode_pending"]
    session.finalize()


def test_joint_capture_keeps_last_accepted_action_after_owner_release(tmp_path):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.motion import JointTarget, MotionSource
    from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["dataset"]["recording_mode"] = "joint"
    runtime = TeleopRuntime(store, FakeRoArm(), FakeO6())
    runtime.attach_robot(FakeRobot())
    target = JointTarget((0.01,) * 6, time.monotonic())
    try:
        lease = runtime.motion.acquire(MotionSource.REPLAY)
        lease.servo_joint(target)
        moving = runtime.dataset_sample()
        lease.release()
        completed = runtime.dataset_sample()
        assert completed["action"][:6] == pytest.approx(target.positions_rad)
        assert completed["action"] == moving["action"]
        assert completed["robot_joint_command"] == pytest.approx(target.positions_rad)
        assert completed["metadata"]["motion_source"] is None
    finally:
        runtime.shutdown(close_devices=False)

@pytest.mark.parametrize("state", ["fault", "closed", "motion_error", "new_owner"])
def test_completed_action_is_not_reused_for_fault_or_new_owner(tmp_path, state):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.motion import JointTarget, MotionSource
    from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["dataset"]["recording_mode"] = "joint"
    runtime = TeleopRuntime(store, FakeRoArm(), FakeO6())
    runtime.attach_robot(FakeRobot())
    try:
        lease = runtime.motion.acquire(MotionSource.REPLAY)
        lease.servo_joint(JointTarget((0.01,) * 6, time.monotonic()))
        lease.release(error="stop failed" if state == "motion_error" else None)
        if state == "new_owner":
            runtime.motion.acquire(MotionSource.POLICY)
        elif state in ("fault", "closed"):
            runtime._set_state(state)
        with pytest.raises(RuntimeError):
            runtime.dataset_sample()
    finally:
        runtime.shutdown(close_devices=False)


def test_completed_tcp_action_is_not_reused_after_motion_error(tmp_path):
    from teleop.gello_cr.app.config_store import TeleopConfigStore
    from teleop.gello_cr.app.runtime import TeleopRuntime
    from teleop.gello_cr.motion import JointTarget, MotionSource
    from teleop.gello_cr.tests.fakes.runtime import FakeO6, FakeRoArm, FakeRobot

    store = TeleopConfigStore(tmp_path / "config.json")
    store.data["dataset"]["recording_mode"] = "tcp"
    runtime = TeleopRuntime(store, FakeRoArm(), FakeO6())
    runtime.attach_robot(FakeRobot())
    try:
        lease = runtime.motion.acquire(MotionSource.REPLAY)
        lease.servo_joint(JointTarget((0.01,) * 6, time.monotonic()))
        lease.release(error="stop failed")
        with pytest.raises(RuntimeError, match="运动|motion"):
            runtime.dataset_sample()
    finally:
        runtime.shutdown(close_devices=False)
