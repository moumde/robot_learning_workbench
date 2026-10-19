from hmi.trainui.services.checkpoint_service import CheckpointService


def test_latest_step(tmp_path):
    (tmp_path / "100" / "params").mkdir(parents=True)
    (tmp_path / "300" / "params").mkdir(parents=True)
    (tmp_path / "200").mkdir()
    assert CheckpointService.latest_step(tmp_path) == 300
