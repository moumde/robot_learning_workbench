from .. import errors
from ..formats import DatasetFormat
from .hdf5 import HDF5Merger
from .lerobot_v3 import LeRobotV3Merger
from .lerobot_v21 import LeRobotV21Merger


def create_merger(format_name, writer_factory):
    mergers = {
        DatasetFormat.LEROBOT_V21: LeRobotV21Merger,
        DatasetFormat.LEROBOT_V3: LeRobotV3Merger,
        DatasetFormat.HDF5: HDF5Merger,
    }
    try:
        return mergers[format_name](writer_factory)
    except KeyError as exc:
        raise errors.UnsupportedDatasetFormat(str(format_name)) from exc
