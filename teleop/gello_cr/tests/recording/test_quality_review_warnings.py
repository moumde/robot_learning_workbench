"""Real writer/validator contract for published quality warnings."""

import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from teleop.gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from teleop.gello_cr.recording.frame import CaptureFrame
from teleop.gello_cr.recording.metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
)
from teleop.gello_cr.recording.schema import IMAGE_KEYS
from teleop.gello_cr.recording.writers.factory import create_writer


@pytest.mark.parametrize("format_name", [DatasetFormat.HDF5, DatasetFormat.LEROBOT_V21])
@pytest.mark.parametrize(
    ("qualities", "expected"),
    [
        (({}, {}, {}), []),
        (({}, {"needs_review": True}, {"needs_review": True}), ["Episodes need review: [1, 2]"]),
    ],
    ids=["clean", "needs-review"],
)
def test_review_flags_are_reported_without_invalidating_real_dataset(
    tmp_path, format_name, qualities, expected
):
    python = sys.executable
    if format_name is DatasetFormat.LEROBOT_V21:
        python = os.environ.get("GELLO_TEST_V21_PYTHON")
        if not python:
            pytest.skip("GELLO_TEST_V21_PYTHON is required for the real V2.1 writer")
    writer = create_writer(DatasetWriterConfig(format_name, worker_python=python))
    session = DatasetSessionMetadata(
        str(uuid4()),
        "quality test",
        "cr3a",
        "o6",
        20,
        (224, 224),
        "joint",
        datetime.now(UTC).isoformat(),
        tmp_path / "capture",
        "quality-test",
    )
    writer.open(session)
    try:
        for index, quality in enumerate(qualities):
            writer.begin_episode(EpisodeMetadata(session.task_name, index, 10.0))
            for frame_index in range(3):
                writer.add_frame(
                    CaptureFrame(
                        10.0 + frame_index / 20,
                        (0.1,) * 12,
                        (0.2,) * 12,
                        {key: np.zeros((224, 224, 3), np.uint8) for key in IMAGE_KEYS},
                        robot_joint_state=(0.1,) * 6,
                        metadata={"recording_mode": "joint"},
                    )
                )
            writer.save_episode(EpisodeResult(EpisodeOutcome.SUCCESS, "", 10.15, 3, quality))
        writer.finalize()
        report = writer.validation_report
        assert report["valid"] and report["errors"] == []
        assert report["episode_count"] == 3 and report["frame_count"] == 9
        assert report["warnings"] == expected
    finally:
        writer.close()
