import sys
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from gello_cr.recording.formats import DatasetFormat, DatasetWriterConfig
from gello_cr.recording.frame import CaptureFrame
from gello_cr.recording.metadata import (
    DatasetSessionMetadata,
    EpisodeMetadata,
    EpisodeOutcome,
    EpisodeResult,
)
from gello_cr.recording.schema import IMAGE_KEYS
from gello_cr.recording.writers.factory import create_writer


@pytest.mark.parametrize("format_name", list(DatasetFormat))
def test_factory_dispatches_without_importing_format_dependencies(format_name):
    writer = create_writer(DatasetWriterConfig(format_name, worker_python=sys.executable))
    assert writer.format_name == format_name.value
    assert writer.capabilities.supports_episode_discard


def test_hdf5_worker_commits_success_failure_and_discards_pending(tmp_path):
    h5py = pytest.importorskip("h5py")
    writer = create_writer(
        DatasetWriterConfig(
            DatasetFormat.HDF5,
            worker_python=sys.executable,
            hdf5_compression="lzf",
        )
    )
    session = DatasetSessionMetadata(
        str(uuid4()),
        "抓取 / motor",
        "cr3a",
        "o6",
        20,
        (16, 16),
        "joint",
        datetime.now(UTC).isoformat(),
        tmp_path / "capture",
        "capture_hdf5",
    )
    writer.open(session)
    try:
        for index, outcome in enumerate(("success", "failure", "discard")):
            writer.begin_episode(EpisodeMetadata(session.task_name, index, 10.0))
            for i in range(3):
                writer.add_frame(
                    CaptureFrame(
                        10.0 + i / 20,
                        (i * 0.1,) * 12,
                        (i * 0.2,) * 12,
                        {key: np.full((16, 16, 3), i, np.uint8) for key in IMAGE_KEYS},
                        robot_joint_state=(i * 0.1,) * 6,
                    robot_tcp_state=(0.5,) * 6 if i == 1 else None,
                        hand_command=(100.0,) * 6,
                        metadata={"recording_mode": "joint"},
                    )
                )
            if outcome == "discard":
                writer.discard_episode()
            else:
                writer.save_episode(
                    EpisodeResult(
                        EpisodeOutcome(outcome),
                        "notes",
                        10.15,
                        3,
                        {},
                    )
                )
        writer.finalize()
        assert writer.validation_report["valid"]
    finally:
        writer.close()
    with h5py.File(session.root / "dataset.hdf5", "r") as file:
        assert list(file["episodes"]) == ["000000", "000001"]
        assert "pending_episode" not in file
        assert file["metadata"].attrs["dataset_id"] == session.dataset_id
        assert file["metadata"].attrs["schema_version"] == "cr3_o6_joint_abs_v1"
        for index, outcome in enumerate(("success", "failure")):
            episode = file[f"episodes/{index:06d}"]
            assert episode["metadata"].attrs["outcome"] == outcome
            np.testing.assert_allclose(episode["timestamp"][:], [10, 10.05, 10.1])
            np.testing.assert_allclose(episode["action/value"][:, 0], [0, 0.2, 0.4])
            assert episode["observation/state"].shape == (3, 12)
            assert episode["action/hand"].shape == (3, 6)
            np.testing.assert_array_equal(episode["valid/robot_tcp_state"][:], [False, True, False])
            np.testing.assert_allclose(episode["observation/tcp"][1], .5)
            assert np.isnan(episode["observation/tcp"][0]).all()
            assert episode["observation/images/base_0_rgb"].compression == "lzf"
            np.testing.assert_array_equal(episode["observation/images/base_0_rgb"][2], 2)
    from gello_cr.recording.validators import HDF5Validator

    assert HDF5Validator().validate(session.root).valid
    with h5py.File(session.root / "dataset.hdf5", "r+") as file:
        file["episodes/000000/action/value"].resize(2, axis=0)
    report = HDF5Validator().validate(session.root)
    assert not report.valid and report.errors
