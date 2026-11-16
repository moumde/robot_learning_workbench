"""Batch orchestration around a single segment RecordingSession."""

import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .errors import RecordingError
from .formats import DatasetFormat
from .manifest import (
    PROFILE_FIELDS,
    BatchLock,
    BatchManifest,
    BatchStatus,
    SegmentManifest,
    SegmentStatus,
    now,
    read_json,
)
from .merge import publish_batch
from .metadata import DatasetSessionMetadata, session_manifest
from .segment import SegmentWriter, episode_records, is_partial, selected_records
from .writers.factory import WriterFactory


def recording_profile(
    *,
    mode,
    fps,
    image_size,
    robot_type="cr3a",
    hand_type="o6",
    camera_configuration=(),
    hardware_profile=None,
):
    metadata = DatasetSessionMetadata(
        "", "", robot_type, hand_type, fps, tuple(image_size), mode, "", Path("."), ""
    )
    schema = session_manifest(metadata, "")
    # JSON-normalized values make persisted and live profiles comparable.
    import json

    profile = {
        key: schema[key]
        for key in (
            "robot_type",
            "hand_type",
            "recording_mode",
            "fps",
            "image_size",
            "camera_keys",
            "observation_fields",
            "action_fields",
            "schema_version",
            "schema_hash",
        )
    }
    profile.update(
        camera_configuration=camera_configuration,
        hardware_profile=hardware_profile or {},
        observation_dim=len(schema["observation_fields"]),
        action_dim=len(schema["action_fields"]),
    )
    return json.loads(json.dumps(profile))


class BatchManager:
    def __init__(
        self, session, *, staging_root, profile_provider, writer_factory=None, event_callback=None
    ):
        self.session = session
        self.writer_factory = writer_factory or session.writer_factory
        self.staging_root = Path(staging_root).expanduser().resolve()
        self.profile_provider = profile_provider
        self._event = event_callback or session.event_callback
        self._batch = self._segment = self._segment_writer = self._batch_lock = None
        self._records = []
        self._lock = threading.RLock()
        # Manifest durability remains serialized, independently of fast UI reads.
        self._manifest_lock = threading.RLock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self._last_error = ""
        self._final_root = ""
        self._final_validation = None
        self._final_dataset_id = ""
        from .recovery import RecoveryManager

        self.recovery = RecoveryManager(self)
        self._recoverable = self.recovery.scan()

    def __getattr__(self, name):
        return getattr(self.session, name)

    def batch_root(self, batch_id):
        if Path(batch_id).name != batch_id or batch_id in (".", ".."):
            raise ValueError("Invalid batch_id")
        return self.staging_root / batch_id

    def _factory_for(self, batch):
        factory = WriterFactory(
            replace(
                self.writer_factory.config,
                format=DatasetFormat(batch.dataset_format),
                **batch.writer_options,
            ),
            worker_pythons=self.writer_factory.worker_pythons,
        )
        # Resume, validation and final merge must use the same interpreter
        # selection as a newly created batch, even after a process restart.
        factory.prepare_environment(event_callback=self._event, allow_install=False)
        self.writer_factory.worker_pythons.update(factory.worker_pythons)
        return factory

    def prepare_dataset(self, task, base_root, *, task_description="", allow_environment_setup=False):
        return self.create_dataset(
            task, base_root, task_description=task_description,
            allow_environment_setup=allow_environment_setup,
        )

    def create_dataset(self, task, base_root, *, task_description="", allow_environment_setup=False):
        if self._batch is not None:
            raise RecordingError("请先完成或保留当前批次，再创建新数据集")
        task = str(task).strip()
        if not task:
            raise ValueError("Dataset task text cannot be empty")
        prepare = getattr(self.writer_factory, "prepare_environment", None)
        if callable(prepare):
            prepare(event_callback=self._event, allow_install=allow_environment_setup)
        config = self.writer_factory.config
        batch = BatchManifest(
            str(uuid4()),
            task,
            self.writer_factory.format_name,
            deepcopy(self.profile_provider()),
            str(Path(base_root).expanduser().resolve()),
            task_description=task_description.strip(),
            writer_options={
                "repo_prefix": config.repo_prefix,
                "video_codec": config.video_codec,
                "hdf5_compression": config.hdf5_compression,
            },
        )
        root = self.batch_root(batch.batch_id)
        lock = BatchLock(root).acquire()
        batch.save(root)
        self._batch, self._batch_lock, self._records = batch, lock, []
        self._final_root, self._final_validation, self._final_dataset_id = "", None, ""
        self._event("info", f"Batch created · batch_id={batch.batch_id}")
        try:
            self._new_segment()
        except Exception as exc:
            self._failed_open(exc)
            raise
        return self.session.snapshot()["root"]

    def _new_segment(self):
        batch = self._batch
        root = self.batch_root(batch.batch_id)
        number = len(batch.segments)
        while (root / f"segment_{number:03d}").exists():
            number += 1
        segment_id = f"segment_{number:03d}"
        segment = SegmentManifest(
            segment_id,
            batch.batch_id,
            str(uuid4()),
            batch.dataset_format,
            batch.profile,
            batch.next_episode_index,
        )
        segment_root = root / segment_id
        segment.save(segment_root)
        batch.segments.append(segment_id)
        batch.status, batch.last_error = BatchStatus.IN_PROGRESS, ""
        batch.save(root)
        self._segment = segment
        profile = batch.profile
        metadata = DatasetSessionMetadata(
            segment.dataset_id,
            batch.task_name,
            profile["robot_type"],
            profile["hand_type"],
            profile["fps"],
            tuple(profile["image_size"]),
            profile["recording_mode"],
            segment.started_at,
            segment_root / "dataset",
            segment_id,
        )
        writer = SegmentWriter(
            self._factory_for(batch)(),
            segment_root,
            batch_id=batch.batch_id,
            segment_id=segment_id,
            allocate=self._allocate_episode,
            on_change=self._episode_changed,
        )
        self.session.open_writer(writer, metadata)
        self._segment_writer = writer
        self._last_error = ""
        self._start_heartbeat()
        self._event("info", f"Segment opened · batch_id={batch.batch_id} · segment={segment_id}")

    def _allocate_episode(self):
        with self._manifest_lock:
            with self._lock:
                index = self._batch.next_episode_index
                self._batch.next_episode_index += 1
                batch = deepcopy(self._batch)
                self._segment.episode_end_index = index
            batch.save(self.batch_root(batch.batch_id))
            return index

    def _episode_changed(self, record):
        with self._lock:
            if not any(item is record for item in self._records):
                self._records.append(record)
        if record["status"] == "saved":
            self._event("info", f"Episode saved · index={record['episode_index']}")
        self._checkpoint()

    def _checkpoint(self):
        writer = self._segment_writer
        if writer is not None:
            writer.checkpoint()
        with self._manifest_lock:
            with self._lock:
                if self._segment is None or self._segment.status != SegmentStatus.ACTIVE:
                    return
                self._segment.frame_count = sum(
                    r["frame_count"]
                    for r in self._records
                    if r["segment_id"] == self._segment.segment_id
                )
                self._segment.last_update_at = now()
                segment = deepcopy(self._segment)
                root = self.batch_root(self._batch.batch_id) / segment.segment_id
            segment.save(root)

    def _start_heartbeat(self):
        self._stop_heartbeat()
        self._heartbeat_stop.clear()

        def heartbeat():
            while not self._heartbeat_stop.wait(3.0):
                try:
                    self._checkpoint()
                except Exception as exc:
                    self._last_error = f"Manifest checkpoint failed: {exc}"
                    self._event("error", self._last_error)
                    self.session.stop_episode()
                    return

        self._heartbeat_thread = threading.Thread(
            target=heartbeat, name="Batch-Heartbeat", daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self):
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)
            if thread.is_alive():
                raise RecordingError("Batch heartbeat did not stop")
        self._heartbeat_thread = None

    def _close_segment(self, *, interrupted=False, reason=""):
        if interrupted:
            self.session.stop_episode()
        self._stop_heartbeat()
        self._checkpoint()
        if interrupted:
            self.session.release_writer()
        else:
            self.session.finalize()
        if self._segment is not None and self._segment.status == SegmentStatus.ACTIVE:
            self._segment.status = (
                SegmentStatus.INTERRUPTED if interrupted else SegmentStatus.COMPLETED
            )
            self._segment.ended_at, self._segment.reason = now(), reason
            self._segment.save(self.batch_root(self._batch.batch_id) / self._segment.segment_id)

    def start_episode(self, task, base_root, *, metadata=None):
        requested = Path(base_root).expanduser().resolve()
        if self._batch is not None and requested != Path(self._batch.output_root):
            self.finalize()
        if self._batch is None:
            self.create_dataset(
                task, requested, task_description=(metadata or {}).get("task_description", "")
            )
        if not self.session.snapshot().get("session_active"):
            self._new_segment()
        parent = self.batch_root(self._batch.batch_id) / self._segment.segment_id
        description = self._batch.task_description or task
        return self.session.start_episode(description, parent, metadata=metadata)

    def stop_episode(self):
        return self.session.stop_episode()

    def save_episode(self, outcome="success", notes=""):
        return self.session.save_episode(outcome, notes)

    def discard_episode(self):
        return self.session.discard_episode()

    def suspend(self, reason="operator suspension"):
        if self._batch is None:
            return
        self._close_segment(interrupted=True, reason=reason)
        self._batch.status = BatchStatus.RECOVERABLE
        self._batch.save(self.batch_root(self._batch.batch_id))
        self._release_batch()
        self.refresh_recovery()

    def preserve_failed_session(self):
        if not (self._last_error or self.session.snapshot().get("error")):
            raise RecordingError("会话没有错误，请正常完成数据集")
        self.suspend(self._last_error or self.session.snapshot()["error"])

    def _failed_open(self, exc):
        self._batch.status, self._batch.last_error = BatchStatus.FAILED, str(exc)
        self._batch.save(self.batch_root(self._batch.batch_id))
        self._release_batch()
        self.refresh_recovery()

    def _release_batch(self):
        self._stop_heartbeat()
        if self._batch_lock is not None:
            self._batch_lock.release()
        self._batch = self._segment = self._segment_writer = self._batch_lock = None
        self._records = []

    def finalize(self):
        if self._batch is None:
            return self._final_root or None
        snapshot = self.session.snapshot()
        if snapshot.get("episode_active") or snapshot.get("episode_pending"):
            raise RecordingError("当前 Episode 未处理；请先保存或丢弃")
        batch = self._batch
        root = self.batch_root(batch.batch_id)
        try:
            if self.session.snapshot().get("session_active"):
                self._close_segment()
            records = episode_records(root, batch.segments)
            if not selected_records(records) and not any(
                is_partial(r) and not r["resolution"] for r in records
            ):
                self.recovery.discard(batch.batch_id)
                self._event("info", "Empty batch closed; no training dataset published")
                return None
            final = self.recovery.published_result(batch, root)
            if final is None:
                final = publish_batch(batch, root, self._factory_for(batch), event=self._event)
        except Exception as exc:
            self._last_error = batch.last_error = str(exc)
            batch.status = BatchStatus.FAILED
            batch.save(root)
            raise
        self._final_root = str(final)
        self._final_validation = read_json(final / "batch_provenance.json")["validation"]
        self._final_dataset_id = batch.final_dataset_id
        self._last_error = ""
        self._release_batch()
        self.refresh_recovery()
        return str(final)

    def close(self):
        return self.finalize()

    def refresh_recovery(self):
        self._recoverable = self.recovery.scan()
        return self._recoverable

    def snapshot(self):
        value = dict(self.session.snapshot())
        with self._lock:
            batch = self._batch
            if batch is not None:
                records = self._records
                current_record = getattr(self._segment_writer, "record", None)
                value.update(
                    session_active=True,
                    batch_task=batch.task_name,
                    task_description=batch.task_description,
                    output_root=batch.output_root,
                    batch_id=batch.batch_id,
                    batch_status=batch.status,
                    segment_id=self._segment.segment_id if self._segment else "",
                    next_episode_index=batch.next_episode_index,
                    local_episode_index=value.get("episode_index"),
                    episode_index=current_record["episode_index"]
                    if current_record is not None
                    else None,
                    format=batch.dataset_format,
                    saved_episodes=len(selected_records(records)),
                    success_episodes=sum(
                        (r.get("result") or {}).get("outcome") == "success"
                        for r in selected_records(records)
                    ),
                    failure_episodes=sum(
                        (r.get("result") or {}).get("outcome") == "failure"
                        or r.get("resolution") == "failure"
                        for r in selected_records(records)
                    ),
                    partial_episodes=[
                        {"episode_index": r["episode_index"], "frame_count": r["frame_count"]}
                        for r in records
                        if is_partial(r)
                        and not r.get("resolution")
                        and (
                            r is not getattr(self._segment_writer, "record", None)
                            or not value.get("episode_active")
                            and not value.get("episode_pending")
                        )
                    ],
                )
            else:
                value.update(batch_id="", segment_id="", partial_episodes=[])
                if self._final_root:
                    value.update(
                        root=self._final_root,
                        validation=self._final_validation,
                        dataset_id=self._final_dataset_id,
                        saved_episodes=self._final_validation["episode_count"],
                    )
            value["recoverable_batches"] = list(self._recoverable)
            if self._last_error:
                value["error"] = self._last_error
        return value

    def _resume(self, batch_id):
        if self._batch is not None:
            raise RecordingError("请先处理当前批次")
        root = self.batch_root(batch_id)
        lock = BatchLock(root).acquire()
        previous_config = self.writer_factory.config
        try:
            batch = BatchManifest.load(root)
            if batch.status in (BatchStatus.COMPLETED, BatchStatus.DISCARDED):
                raise RecordingError("Batch is already completed or discarded")
            if batch.final_path and Path(batch.final_path).exists():
                raise RecordingError("Dataset may already be published; finalize this batch first")
            profile = self.profile_provider()
            for key in PROFILE_FIELDS:
                if profile[key] != batch.profile[key]:
                    raise RecordingError(f"Resume blocked: {key} mismatch")
            self.writer_factory.select(batch.dataset_format)
            records = self.recovery.inspect_segments(batch, root)
            self._batch, self._batch_lock, self._records = batch, lock, records
            self._final_root, self._final_validation, self._final_dataset_id = "", None, ""
            batch.next_episode_index = max(
                batch.next_episode_index, max((r["episode_index"] + 1 for r in records), default=0)
            )
            self._new_segment()
        except Exception:
            self.writer_factory.config = previous_config
            if self._batch is None:
                lock.release()
            else:
                self._release_batch()
            raise
        self._event("info", f"Recovery started · batch_id={batch_id}")
        self.refresh_recovery()
        return self.session
