from types import SimpleNamespace

import numpy as np
import pytest

from core.workbench.app.runtime_bindings import RuntimeCommandBindings
from core.workbench.app.service import ApplicationService
from core.workbench.core.state_machine import Command
from core.workbench.recording.formats import DatasetFormat, DatasetWriterConfig
from core.workbench.recording.frame import CaptureFrame
from core.workbench.recording.schema import IMAGE_KEYS
from core.workbench.recording.session import RecordingSession
from core.workbench.recording.writers.factory import WriterFactory


def test_application_locks_format_until_dataset_is_finalized(tmp_path):
    class Writer:
        def __init__(self, format_name):
            self.format_name = format_name

        def open(self, metadata):
            self.metadata = metadata

        def finalize(self):
            pass

        def close(self):
            pass

    class Factory(WriterFactory):
        def __call__(self):
            return Writer(self.format_name)

    factory = Factory(DatasetWriterConfig())
    frame = CaptureFrame(
        1.0,
        (0.0,) * 12,
        (0.0,) * 12,
        {k: np.zeros((2, 2, 3), np.uint8) for k in IMAGE_KEYS},
        metadata={"recording_mode": "joint"},
    )
    recorder = RecordingSession(
        SimpleNamespace(capture=lambda: frame), factory, event_callback=lambda *a: None
    )
    service = ApplicationService()
    RuntimeCommandBindings(service, teleop_engine=SimpleNamespace(), recorder=recorder).install()
    service.dispatch(Command.SELECT_DATASET_FORMAT, {"format": "hdf5"})
    service.dispatch(Command.CREATE_DATASET, {"task": "pick / motor", "base_root": str(tmp_path)})
    assert recorder.snapshot()["format"] == "hdf5"
    assert recorder.snapshot()["session_active"]
    assert not recorder.snapshot()["episode_active"]
    assert "pick_motor_" in recorder.snapshot()["root"]
    with pytest.raises(RuntimeError, match="切换格式"):
        service.dispatch(Command.SELECT_DATASET_FORMAT, {"format": "lerobot_v21"})
    assert factory.config.format == DatasetFormat.HDF5
    service.dispatch(Command.FINALIZE_DATASET)
    service.dispatch(Command.SELECT_DATASET_FORMAT, {"format": "lerobot_v21"})
    assert recorder.snapshot()["format"] == "lerobot_v21"
