from .base import JournalDatasetMerger


class LeRobotV21Merger(JournalDatasetMerger):
    """Rebuild V2.1 parquet, tasks, videos and statistics through the official SDK."""

    format_name = "lerobot_v21"
