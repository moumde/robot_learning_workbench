"""Named Parquet trajectories with JSON metadata. No hardware dependencies."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from .model import Trajectory, TrajectoryFrame, TrajectoryMetadata
from .validation import VECTOR_FIELDS, validate_trajectory


class TrajectoryStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def _path(self, trajectory_id):
        return self.root / str(UUID(trajectory_id))

    @staticmethod
    def _read_metadata(path):
        values = json.loads(path.read_text(encoding="utf-8"))
        if values.get("joint_mask") is not None:
            values["joint_mask"] = tuple(values["joint_mask"])
        return TrajectoryMetadata(**values)

    def save(self, trajectory: Trajectory) -> Path:
        import pyarrow as pa
        import pyarrow.parquet as pq

        validate_trajectory(trajectory)
        destination = self._path(trajectory.metadata.trajectory_id)
        if destination.exists():
            raise FileExistsError(f"Trajectory already exists: {trajectory.metadata.trajectory_id}")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".saving-", dir=self.root))
        try:
            schema = pa.schema(
                [("timestamp", pa.float64())]
                + [(name, pa.list_(pa.float64())) for name in VECTOR_FIELDS]
            )
            pq.write_table(
                pa.Table.from_pylist([asdict(f) for f in trajectory.frames], schema=schema),
                temporary / "trajectory.parquet",
            )
            (temporary / "meta.json").write_text(
                json.dumps(asdict(trajectory.metadata), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return destination

    def load(self, trajectory_id) -> Trajectory:
        import pyarrow.parquet as pq

        directory = self._path(trajectory_id)
        metadata = self._read_metadata(directory / "meta.json")
        if metadata.trajectory_id != str(UUID(trajectory_id)):
            raise ValueError("Trajectory ID does not match its directory")
        frames = []
        for row in pq.read_table(directory / "trajectory.parquet").to_pylist():
            frames.append(
                TrajectoryFrame(
                    row["timestamp"],
                    **{
                        field: tuple(row[field]) if row[field] is not None else None
                        for field in VECTOR_FIELDS
                    },
                )
            )
        trajectory = Trajectory(metadata.name, tuple(frames), metadata)
        validate_trajectory(trajectory)
        return trajectory

    def list(self):
        if not self.root.exists():
            return []
        return sorted(
            (
                self._read_metadata(path)
                for path in self.root.glob("*/meta.json")
                if not path.parent.name.startswith(".")
            ),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def delete(self, trajectory_id):
        directory = self._path(trajectory_id)
        if directory.is_symlink():
            raise ValueError("Refusing trajectory directory symlink")
        shutil.rmtree(directory)
