"""Explicit backend selection; adding a writer does not change session logic."""

from dataclasses import asdict, replace

from ..errors import UnsupportedDatasetFormat
from ..formats import DatasetFormat, DatasetWriterConfig
from .base import DatasetWriter


class WriterFactory:
    """Selected configuration for the next dataset; no open writer is mutated."""

    def __init__(self, config: DatasetWriterConfig, *, worker_pythons=None):
        self.config = config
        self.worker_pythons = dict(worker_pythons or {})

    @property
    def format_name(self):
        return self.config.format.value

    def select(self, format_name):
        try:
            self.config = replace(self.config, format=DatasetFormat(format_name))
        except ValueError as exc:
            raise UnsupportedDatasetFormat(str(format_name)) from exc

    def __call__(self):
        python = self.worker_pythons.get(self.format_name, self.config.worker_python)
        return create_writer(replace(self.config, worker_python=python))

    def prepare_environment(self, *, event_callback=None, allow_install=True, format_name=None):
        from .environment import prepare_writer_environment

        format_name = format_name or self.format_name
        python = self.worker_pythons.get(format_name, self.config.worker_python)
        selected = prepare_writer_environment(
            format_name, python, event_callback=event_callback, allow_install=allow_install
        )
        self.worker_pythons[format_name] = selected


def create_writer(format_name: str | DatasetWriterConfig, **options) -> DatasetWriter:
    if isinstance(format_name, DatasetWriterConfig):
        settings = asdict(format_name)
        format_name = settings.pop("format")
        options = {**settings, **options}
    if format_name == DatasetFormat.LEROBOT_V3:
        from .lerobot_v3 import LeRobotV3Writer

        return LeRobotV3Writer(**options)
    if format_name == DatasetFormat.LEROBOT_V21:
        from .lerobot_v21 import LeRobotV21Writer

        return LeRobotV21Writer(**options)
    if format_name == DatasetFormat.HDF5:
        from .hdf5 import HDF5Writer

        return HDF5Writer(**options)
    raise UnsupportedDatasetFormat(f"Unsupported dataset format: {format_name}")


def create_worker_service(format_name):
    """Load heavy dependencies only after the worker receives init."""
    if format_name == DatasetFormat.LEROBOT_V3:
        from lerobot.configs.video import RGBEncoderConfig
        from lerobot.datasets.lerobot_dataset import CODEBASE_VERSION, LeRobotDataset

        if not CODEBASE_VERSION.startswith("v3."):
            raise UnsupportedDatasetFormat("V3 writer requires a LeRobot V3 worker environment")
        from .lerobot_v3_worker import LeRobotV3WorkerService

        return LeRobotV3WorkerService(LeRobotDataset.create, RGBEncoderConfig)
    if format_name == DatasetFormat.LEROBOT_V21:
        from .lerobot_v21_worker import LeRobotV21WorkerService

        return LeRobotV21WorkerService()
    if format_name == DatasetFormat.HDF5:
        from .hdf5_worker import HDF5WorkerService

        return HDF5WorkerService()
    raise UnsupportedDatasetFormat(f"Unsupported dataset format: {format_name}")


def create_validator(format_name):
    from ..validators import HDF5Validator, LeRobotV3Validator, LeRobotV21Validator

    validators = {
        DatasetFormat.LEROBOT_V21: LeRobotV21Validator,
        DatasetFormat.LEROBOT_V3: LeRobotV3Validator,
        DatasetFormat.HDF5: HDF5Validator,
    }
    try:
        return validators[format_name]()
    except KeyError as exc:
        raise UnsupportedDatasetFormat(str(format_name)) from exc


def detect_format(root):
    import json

    if (root / "dataset.hdf5").is_file():
        return DatasetFormat.HDF5
    version = json.loads((root / "meta/info.json").read_text())["codebase_version"]
    if version == "v2.1":
        return DatasetFormat.LEROBOT_V21
    if version.startswith("v3."):
        return DatasetFormat.LEROBOT_V3
    raise UnsupportedDatasetFormat(f"Unsupported LeRobot version: {version}")
