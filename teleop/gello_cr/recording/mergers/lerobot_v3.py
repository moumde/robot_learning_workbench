from .base import JournalDatasetMerger


class LeRobotV3Merger(JournalDatasetMerger):
    """Rebuild V3 tables, video intervals and metadata through the official SDK."""

    format_name = "lerobot_v3"
