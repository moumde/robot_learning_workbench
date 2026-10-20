from .base import JournalDatasetMerger


class HDF5Merger(JournalDatasetMerger):
    """Write a fresh HDF5 file from retained episodes, including raw RGB arrays."""

    format_name = "hdf5"
