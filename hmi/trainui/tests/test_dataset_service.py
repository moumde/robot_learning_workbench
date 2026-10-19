import json
from pathlib import Path

from hmi.trainui.models import ConfigInfo
from hmi.trainui.services.dataset_service import DatasetService


def _config(tmp_path: Path, *, expected_state_dim=7, expected_action_dim=7) -> ConfigInfo:
    return ConfigInfo(
        name="pi05_custom_lora",
        project_name="openpi",
        default_exp_name="",
        model_type="pi05",
        model_class="Pi0Config",
        pi05=True,
        action_dim=32,
        action_horizon=30,
        max_token_len=200,
        paligemma_variant="gemma_2b_lora",
        action_expert_variant="gemma_300m_lora",
        data_factory="LeRobotCustomDataConfig",
        dataset_mode="lerobot",
        dataset_override_supported=True,
        default_repo_id="data_v21",
        default_asset_id="local/data_v21",
        asset_binding_mode="prefix",
        asset_id_prefix="local",
        required_features=(
            "observation.images.front",
            "observation.state",
            "action",
        ),
        expected_state_dim=expected_state_dim,
        expected_action_dim=expected_action_dim,
        contract_source="RepackTransform",
        assets_dir=tmp_path / "assets" / "pi05_custom_lora",
        checkpoint_base_dir=tmp_path / "checkpoints",
        weight_loader_class="CheckpointWeightLoader",
        weight_path="gs://x/params",
        batch_size=16,
        num_train_steps=100000,
        log_interval=100,
        save_interval=10000,
        keep_period=5000,
        num_workers=2,
        seed=42,
        fsdp_devices=1,
        wandb_enabled=True,
        ema_decay=None,
        lr_schedule_type="CosineDecaySchedule",
        warmup_steps=1000,
        peak_lr=1e-4,
        decay_steps=20000,
        decay_lr=1e-5,
        optimizer_type="AdamW",
        clip_gradient_norm=1.0,
        norm_stats_supported=True,
        runnable=True,
        runnable_reason="",
    )


def _write_dataset(root: Path, *, state_dim=7, action_dim=7):
    meta = root / "data_v21" / "meta"
    meta.mkdir(parents=True)
    features = {
        "observation.images.front": {"dtype": "video", "shape": [480, 640, 3]},
        "observation.state": {"dtype": "float32", "shape": [state_dim]},
        "action": {"dtype": "float32", "shape": [action_dim]},
    }
    (meta / "info.json").write_text(json.dumps({
        "fps": 30,
        "total_episodes": 70,
        "total_frames": 7000,
        "features": features,
    }))


def test_discover_uses_config_contract(tmp_path):
    root = tmp_path / "train"
    _write_dataset(root)
    result = DatasetService(root).discover(_config(tmp_path))
    assert len(result) == 1
    assert result[0].valid
    assert result[0].state_dim == 7
    assert result[0].action_dim == 7


def test_dimension_check_only_when_config_declares_dimension(tmp_path):
    root = tmp_path / "train"
    _write_dataset(root, state_dim=11, action_dim=9)
    result = DatasetService(root).discover(
        _config(tmp_path, expected_state_dim=None, expected_action_dim=None)
    )
    assert result[0].valid
    assert result[0].state_dim == 11
    assert result[0].action_dim == 9


def test_asset_binding_is_config_driven(tmp_path):
    config = _config(tmp_path)
    assert config.asset_id_for_dataset("new_data") == "local/new_data"
    assert config.norm_stats_path("new_data") == (
        tmp_path / "assets" / "pi05_custom_lora" / "local" / "new_data" / "norm_stats.json"
    )


def test_missing_simple_config_repo_is_blocked(tmp_path):
    config = _config(tmp_path)
    service = DatasetService(tmp_path / "train")
    source = service.configured_source(config)
    assert source is not None
    assert not source.valid
    assert source.source == "config-missing"
    assert "meta/info.json" in source.errors[0]


def test_namespaced_config_repo_is_remote_candidate(tmp_path):
    config = _config(tmp_path)
    config = ConfigInfo(**{**config.__dict__, "default_repo_id": "org/dataset"})
    service = DatasetService(tmp_path / "train")
    source = service.configured_source(config)
    assert source is not None
    assert source.valid
    assert source.source == "config-remote"


def test_nested_local_repo_is_discovered(tmp_path):
    root = tmp_path / "train"
    meta = root / "org" / "dataset" / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text(json.dumps({
        "fps": 30,
        "total_episodes": 1,
        "total_frames": 10,
        "features": {
            "observation.images.front": {"shape": [10, 10, 3]},
            "observation.state": {"shape": [7]},
            "action": {"shape": [7]},
        },
    }))
    result = DatasetService(root).discover(_config(tmp_path))
    assert [x.repo_id for x in result] == ["org/dataset"]
    assert result[0].valid
