from __future__ import annotations

import dataclasses
from pathlib import PurePosixPath
import re
from typing import Any

from openpi.training import config as training_config

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_REPO_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_leaf_name(value: str, label: str) -> str:
    value = value.strip()
    if not value or not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{label} 仅允许字母、数字、点、下划线和连字符: {value!r}")
    return value


def _validate_repo_id(value: str, label: str = "dataset_id") -> str:
    """Validate a relative repo id without assuming it is a single path leaf.

    OpenPI configs may use local ids such as ``three_stack`` or namespaced
    repository ids such as ``physical-intelligence/aloha_pen_uncap_diverse``.
    Absolute paths and parent traversal are deliberately rejected.
    """
    value = value.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(not _SAFE_REPO_SEGMENT.fullmatch(part) for part in path.parts)
    ):
        raise ValueError(
            f"{label} 必须是安全的相对 repo_id（可使用 namespace/name）: {value!r}"
        )
    return value


def _field_names(value: Any) -> set[str]:
    if not dataclasses.is_dataclass(value):
        return set()
    return {field.name for field in dataclasses.fields(value)}


def asset_id_for_dataset(base: Any, dataset_id: str) -> str | None:
    """Resolve the new asset id using only the selected config's current binding.

    Rules:
    - no explicit asset id -> keep None so OpenPI follows repo_id
    - asset id == old repo -> follow the new repo
    - asset id ends in /<old repo> -> preserve prefix, replace only the repo leaf
    - any other explicit asset id -> fixed robot/shared asset, keep unchanged
    """
    data = base.data
    assets = getattr(data, "assets", None)
    old_repo = getattr(data, "repo_id", None)
    old_repo = old_repo if isinstance(old_repo, str) and old_repo else None
    old_asset = getattr(assets, "asset_id", None) if assets is not None else None
    old_asset = old_asset if isinstance(old_asset, str) and old_asset else None

    if old_asset is None:
        return None
    if old_repo and old_asset == old_repo:
        return dataset_id
    if old_repo and old_asset.endswith("/" + old_repo):
        parent = str(PurePosixPath(old_asset).parent)
        return dataset_id if parent == "." else f"{parent}/{dataset_id}"
    return old_asset


def with_dataset(base: Any, dataset_id: str | None):
    if dataset_id is None:
        return base

    dataset_id = _validate_repo_id(dataset_id, "dataset_id")
    data = base.data

    # Selecting the config-declared repo means "use the original DataConfig".
    # Do not rebuild it unnecessarily; this preserves remote repo ids, assets
    # and any factory-specific semantics exactly as registered in OpenPI.
    old_repo = getattr(data, "repo_id", None)
    if isinstance(old_repo, str) and old_repo == dataset_id:
        return base
    data_fields = _field_names(data)
    if not dataclasses.is_dataclass(data) or "repo_id" not in data_fields:
        raise ValueError(
            f"当前 DataConfigFactory 不支持数据集 repo_id 覆盖: {type(data).__name__}"
        )

    changes: dict[str, Any] = {"repo_id": dataset_id}
    if "assets" in data_fields:
        assets = getattr(data, "assets", None)
        if dataclasses.is_dataclass(assets):
            asset_fields = _field_names(assets)
            if "asset_id" in asset_fields:
                changes["assets"] = dataclasses.replace(
                    assets,
                    asset_id=asset_id_for_dataset(base, dataset_id),
                )

    return dataclasses.replace(base, data=dataclasses.replace(data, **changes))


def _replace_supported_fields(obj: Any, values: dict[str, Any]) -> Any:
    """dataclasses.replace only fields actually declared by this config type.

    This is what makes TrainUI work with different schedulers/optimizers.  A
    control that is not part of the selected config is ignored and the original
    OpenPI object is preserved unchanged.
    """
    if not dataclasses.is_dataclass(obj):
        return obj
    fields = _field_names(obj)
    updates = {key: value for key, value in values.items() if key in fields and value is not None}
    return dataclasses.replace(obj, **updates) if updates else obj


def build_train_config(spec: dict[str, Any]):
    config_name = _validate_leaf_name(str(spec["config_name"]), "config_name")
    dataset_raw = spec.get("dataset_id")
    dataset_id = None if dataset_raw in (None, "") else _validate_repo_id(str(dataset_raw), "dataset_id")
    exp_name = _validate_leaf_name(str(spec["exp_name"]), "exp_name")

    base = training_config.get_config(config_name)
    base = with_dataset(base, dataset_id)

    mode = str(spec.get("run_mode", "new"))
    if mode not in {"new", "resume", "overwrite"}:
        raise ValueError(f"不支持的 run_mode: {mode}")

    num_train_steps = int(spec["num_train_steps"])
    batch_size = int(spec["batch_size"])
    save_interval = int(spec["save_interval"])
    log_interval = int(spec["log_interval"])
    num_workers = int(spec["num_workers"])
    seed = int(spec["seed"])
    fsdp_devices = int(spec["fsdp_devices"])
    keep_period_raw = spec.get("keep_period")
    keep_period = None if keep_period_raw in (None, 0) else int(keep_period_raw)

    for name, value in {
        "num_train_steps": num_train_steps,
        "batch_size": batch_size,
        "save_interval": save_interval,
        "log_interval": log_interval,
        "fsdp_devices": fsdp_devices,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} 必须大于 0")
    if num_workers < 0:
        raise ValueError("num_workers 不能小于 0")
    if keep_period is not None and keep_period <= 0:
        raise ValueError("keep_period 必须大于 0 或设为 0 表示禁用")

    def optional_int(name: str) -> int | None:
        value = spec.get(name)
        return None if value is None else int(value)

    def optional_float(name: str) -> float | None:
        value = spec.get(name)
        return None if value is None else float(value)

    warmup_steps = optional_int("warmup_steps")
    decay_steps = optional_int("decay_steps")
    peak_lr = optional_float("peak_lr")
    decay_lr = optional_float("decay_lr")
    clip_gradient_norm = optional_float("clip_gradient_norm")

    if warmup_steps is not None and warmup_steps < 0:
        raise ValueError("warmup_steps 不能小于 0")
    if decay_steps is not None and decay_steps <= 0:
        raise ValueError("decay_steps 必须大于 0")
    if warmup_steps is not None and decay_steps is not None and decay_steps <= warmup_steps:
        raise ValueError("decay_steps 必须大于 warmup_steps")
    if peak_lr is not None and peak_lr <= 0:
        raise ValueError("peak_lr 必须大于 0")
    if decay_lr is not None and decay_lr <= 0:
        raise ValueError("decay_lr 必须大于 0")
    if clip_gradient_norm is not None and clip_gradient_norm <= 0:
        raise ValueError("clip_gradient_norm 必须大于 0")

    lr_schedule = _replace_supported_fields(
        base.lr_schedule,
        {
            "warmup_steps": warmup_steps,
            "peak_lr": peak_lr,
            "decay_steps": decay_steps,
            "decay_lr": decay_lr,
        },
    )
    optimizer = _replace_supported_fields(
        base.optimizer,
        {"clip_gradient_norm": clip_gradient_norm},
    )

    return dataclasses.replace(
        base,
        exp_name=exp_name,
        num_train_steps=num_train_steps,
        batch_size=batch_size,
        save_interval=save_interval,
        log_interval=log_interval,
        keep_period=keep_period,
        num_workers=num_workers,
        lr_schedule=lr_schedule,
        optimizer=optimizer,
        seed=seed,
        fsdp_devices=fsdp_devices,
        wandb_enabled=bool(spec["wandb_enabled"]),
        resume=mode == "resume",
        overwrite=mode == "overwrite",
    )
