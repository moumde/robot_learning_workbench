"""Official LeRobot V2.1 SDK adapter, isolated from the V3 environment."""

from ..errors import UnsupportedDatasetFormat
from .lerobot_v3_schema import dataset_features
from .lerobot_worker import LeRobotWorkerService


class V21Dataset:
    def __init__(self, **kwargs):
        from lerobot.datasets.lerobot_dataset import CODEBASE_VERSION, LeRobotDataset

        if CODEBASE_VERSION != "v2.1":
            raise UnsupportedDatasetFormat(
                "V2.1 writer requires LeRobot 0.3.3 in its own worker environment"
            )
        self.dataset = LeRobotDataset.create(**kwargs)
        self.root = self.dataset.root

    def add_frame(self, frame):
        values = dict(frame)
        task = values.pop("task")
        self.dataset.add_frame(values, task=task)

    def save_episode(self):
        self.dataset.save_episode()

    def clear_episode_buffer(self):
        # SDK 0.3.3 removes image directories without waiting for its image
        # writer. Drain it first so discarded images cannot reappear later.
        self.dataset._wait_image_writer()
        self.dataset.clear_episode_buffer()

    def finalize(self):
        from lerobot.datasets.utils import write_stats

        self.dataset.stop_image_writer()
        write_stats(self.dataset.meta.stats, self.root)
        # Official V2.1 uses episodes_stats.jsonl; retain aggregate stats too.
        for name in ("tasks.jsonl", "episodes.jsonl", "episodes_stats.jsonl"):
            (self.root / "meta" / name).touch(exist_ok=True)


class LeRobotV21WorkerService(LeRobotWorkerService):
    def __init__(self, dataset_factory=V21Dataset):
        super().__init__(dataset_factory, None)

    def _create_dataset(self, request, root, fps, height, width):
        if request.get("video_codec"):
            raise ValueError("V2.1 uses the official SDK's video codec; leave video_codec null")
        return self._dataset_factory(
            repo_id=request["repo_id"],
            root=root,
            fps=fps,
            robot_type="dobot_cr3_o6" if self.recording_mode == "joint" else "dobot_cr5_o6",
            features=dataset_features(height, width, self.recording_mode),
            use_videos=True,
            image_writer_threads=4,
        )
