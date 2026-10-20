"""Read-only discovery and explicit recovery decisions for interrupted batches."""

from pathlib import Path

from .errors import RecordingError
from .journal import read_frames
from .manifest import (
    BatchLock,
    BatchManifest,
    BatchStatus,
    SegmentManifest,
    SegmentStatus,
    atomic_json,
    now,
    read_json,
)
from .merge import publish_batch
from .schema import recording_schema
from .segment import episode_records, is_partial, selected_records
from .validation import validate_capture_frame
from .validation_service import validate_in_worker


class RecoveryManager:
    def __init__(self, manager):
        self.manager = manager

    def scan(self):
        batches = []
        for path in sorted(self.manager.staging_root.glob("*/manifest.json")):
            root = path.parent
            if BatchLock.held(root):
                continue
            try:
                batch = BatchManifest.load(root)
                if batch.status in (BatchStatus.COMPLETED, BatchStatus.DISCARDED):
                    continue
                records = episode_records(root, batch.segments)
                selected = selected_records(records)
                batches.append(
                    {
                        "batch_id": batch.batch_id,
                        "task_name": batch.task_name,
                        "dataset_format": batch.dataset_format,
                        "created_at": batch.created_at,
                        "status": "recoverable",
                        "segments": len(batch.segments),
                        "episodes": len(selected),
                        "frames": sum(r["frame_count"] for r in selected),
                        "partial_episodes": [
                            {"episode_index": r["episode_index"], "frame_count": r["frame_count"]}
                            for r in records
                            if is_partial(r) and not r["resolution"]
                        ],
                        "error": batch.last_error,
                    }
                )
            except Exception as exc:
                batches.append(
                    {
                        "batch_id": root.name,
                        "task_name": root.name,
                        "segments": 0,
                        "episodes": 0,
                        "frames": 0,
                        "partial_episodes": [],
                        "status": "failed",
                        "dataset_format": "unknown",
                        "error": str(exc),
                    }
                )
        return batches

    def inspect_segments(self, batch, root):
        """Called only under the batch lock; never rewrites original data files."""
        records = episode_records(root, batch.segments)
        for segment_id in batch.segments:
            segment = SegmentManifest.load(root / segment_id)
            if segment.status == SegmentStatus.ACTIVE:
                own = [r for r in records if r["segment_id"] == segment_id]
                segment.status = (
                    SegmentStatus.INTERRUPTED
                    if any(is_partial(r) for r in own)
                    else SegmentStatus.COMPLETED
                )
                segment.frame_count = sum(r["frame_count"] for r in own)
                segment.episode_end_index = max((r["episode_index"] for r in own), default=None)
                segment.reason, segment.ended_at = "process_interruption_detected", now()
                segment.save(root / segment_id)
                self.manager._event("warning", f"Process interruption detected · {segment_id}")
        return records

    def resume(self, batch_id):
        return self.manager._resume(batch_id)

    def resolve_partial(self, batch_id, episode_index, decision):
        if decision not in ("failure", "discard"):
            raise ValueError("Partial decision must be failure or discard")
        manager = self.manager
        owned = manager._batch is not None and manager._batch.batch_id == batch_id
        root = manager.batch_root(batch_id)
        lock = None if owned else BatchLock(root).acquire()
        try:
            batch = manager._batch if owned else BatchManifest.load(root)
            if batch.status in (BatchStatus.COMPLETED, BatchStatus.DISCARDED):
                raise RecordingError("Batch is already completed or discarded")
            records = episode_records(root, batch.segments)
            record = next((r for r in records if r["episode_index"] == int(episode_index)), None)
            if record is None or not is_partial(record):
                raise RecordingError("Episode is not partial")
            current = getattr(manager._segment_writer, "record", None) if owned else None
            if current is not None and current["episode_index"] == int(episode_index):
                raise RecordingError("Suspend the current recording before resolving it as partial")
            if decision == "failure":
                previous = None
                count = 0
                for frame in read_frames(record["journal_path"]):
                    validate_capture_frame(
                        frame,
                        recording_schema(batch.profile["recording_mode"]),
                        previous_timestamp=previous,
                    )
                    previous = frame.timestamp
                    count += 1
                if not count:
                    raise RecordingError(
                        "Partial episode has no readable complete frames; discard it"
                    )
            atomic_json(
                root / "resolutions" / f"{int(episode_index):06d}.json",
                {"decision": decision, "decided_at": now(), "needs_review": True},
            )
            if owned:
                for item in manager._records:
                    if item["episode_index"] == int(episode_index):
                        item["resolution"] = decision
            manager._event("warning", f"Partial episode {episode_index}: {decision}")
        finally:
            if lock is not None:
                lock.release()
        manager.refresh_recovery()

    def published_result(self, batch, root):
        if not batch.final_path or not Path(batch.final_path).exists():
            return None
        final = Path(batch.final_path)
        provenance = read_json(final / "batch_provenance.json")
        if (provenance["batch_id"], provenance["dataset_id"]) != (
            batch.batch_id,
            batch.final_dataset_id,
        ):
            raise RecordingError("Published dataset provenance does not match this batch")
        report = validate_in_worker(batch.dataset_format, final, self.manager._factory_for(batch))
        if not report["valid"]:
            raise RecordingError(
                "Published dataset validation FAILED: " + "; ".join(report["errors"])
            )
        batch.status, batch.last_error = BatchStatus.COMPLETED, ""
        batch.save(root)
        self.manager._event("info", f"Dataset publication recovered: {final}")
        return final

    def finalize(self, batch_id):
        manager = self.manager
        if manager._batch is not None:
            if manager._batch.batch_id != batch_id:
                raise RecordingError("请先处理当前批次")
            return manager.finalize()
        root = manager.batch_root(batch_id)
        lock = BatchLock(root).acquire()
        batch = None
        try:
            batch = BatchManifest.load(root)
            if batch.status == BatchStatus.DISCARDED:
                raise RecordingError("Batch was discarded")
            final = self.published_result(batch, root)
            if final is None:
                records = self.inspect_segments(batch, root)
                if not selected_records(records) and not any(
                    is_partial(r) and not r["resolution"] for r in records
                ):
                    batch.status = BatchStatus.DISCARDED
                    batch.save(root)
                    manager._event("info", "Empty batch closed; staging retained")
                    return None
                final = publish_batch(
                    batch, root, manager._factory_for(batch), event=manager._event
                )
            manager._final_root = str(final)
            manager._final_validation = read_json(final / "batch_provenance.json")["validation"]
            manager._final_dataset_id = batch.final_dataset_id
            manager._last_error = ""
            return str(final)
        except Exception as exc:
            if batch is not None and batch.status != BatchStatus.COMPLETED:
                batch.status, batch.last_error = BatchStatus.FAILED, str(exc)
                batch.save(root)
            raise
        finally:
            lock.release()
            manager.refresh_recovery()

    def discard(self, batch_id):
        manager = self.manager
        if manager._batch is not None and manager._batch.batch_id != batch_id:
            raise RecordingError("请先处理当前批次")
        if manager._batch is not None and manager._batch.batch_id == batch_id:
            manager.suspend("operator discarded batch")
        root = manager.batch_root(batch_id)
        lock = BatchLock(root).acquire()
        try:
            batch = BatchManifest.load(root)
            if batch.status == BatchStatus.COMPLETED:
                raise RecordingError("Published batch cannot be discarded")
            batch.status = BatchStatus.DISCARDED
            batch.save(root)
            manager._event("warning", f"Batch discarded; staging retained · batch_id={batch_id}")
        finally:
            lock.release()
        manager.refresh_recovery()
