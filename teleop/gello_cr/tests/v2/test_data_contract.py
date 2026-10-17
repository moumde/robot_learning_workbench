from gello_cr.data_contract import (
    ACTION_DIM,
    ACTION_FIELDS,
    CAMERA_KEYS,
    FPS,
    IMAGE_SIZE,
    STATE_DIM,
    STATE_FIELDS,
)


def test_openpi_contract_is_frozen_during_v2_migration() -> None:
    assert STATE_DIM == 18
    assert ACTION_DIM == 12
    assert len(STATE_FIELDS) == 18
    assert len(ACTION_FIELDS) == 12
    assert FPS == 20
    assert IMAGE_SIZE == (224, 224)
    assert CAMERA_KEYS == ("base_rgb", "wrist_rgb", "roi_rgb")
