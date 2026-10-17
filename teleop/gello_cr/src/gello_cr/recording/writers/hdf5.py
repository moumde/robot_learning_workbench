"""HDF5 writer client; h5py and disk I/O stay in the worker."""

from .base import WriterCapabilities
from .worker_writer import WorkerDatasetWriter


class HDF5Writer(WorkerDatasetWriter):
    format_name = "hdf5"
    capabilities = WriterCapabilities(False, True, True, True)
