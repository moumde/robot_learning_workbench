"""Official V3 SDK creation and encoding settings."""

from __future__ import annotations

from .lerobot_v3_schema import dataset_features
from .lerobot_worker import LeRobotWorkerService


class LeRobotV3WorkerService(LeRobotWorkerService):
    def _create_dataset(self, request, root, fps, height, width):
        encoder = self._encoder_factory(
            vcodec=request.get("video_codec") or "h264",
            pix_fmt="yuv420p",
            crf=18,
            preset="fast",
            g=fps,
        )
        return self._dataset_factory(
            repo_id=str(request["repo_id"]),
            root=root,
            fps=fps,
            robot_type="dobot_cr3_o6" if self.recording_mode == "joint" else "dobot_cr5_o6",
            features=dataset_features(height, width, self.recording_mode),
            use_videos=True,
            rgb_encoder=encoder,
            streaming_encoding=True,
            encoder_queue_maxsize=max(4, fps // 2),
            encoder_threads=2,
            batch_encoding_size=1,
        )
