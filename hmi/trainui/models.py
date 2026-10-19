from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any


class TrainState(str, Enum):
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class RunMode(str, Enum):
    NEW = "new"
    RESUME = "resume"
    OVERWRITE = "overwrite"


@dataclass(frozen=True)
class DatasetInfo:
    repo_id: str
    path: Path
    total_episodes: int | None
    total_frames: int | None
    fps: float | None
    state_dim: int | None
    action_dim: int | None
    features: tuple[str, ...]
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source: str = "local"

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.total_episodes is not None:
            parts.append(f"回合 {self.total_episodes}")
        if self.total_frames is not None:
            parts.append(f"帧数 {self.total_frames}")
        if self.fps is not None:
            parts.append(f"{self.fps:g} Hz")
        if self.state_dim is not None:
            parts.append(f"状态 {self.state_dim}D")
        if self.action_dim is not None:
            parts.append(f"动作 {self.action_dim}D")
        if self.source != "local":
            parts.append("配置数据源")
        return " · ".join(parts) if parts else self.repo_id


@dataclass(frozen=True)
class ConfigInfo:
    """TrainUI's read-only view of one registered OpenPI TrainConfig.

    The UI intentionally does not encode robot names.  Everything here is
    derived from the selected OpenPI config and its data factory.
    """

    name: str
    project_name: str
    default_exp_name: str

    model_type: str
    model_class: str
    pi05: bool
    action_dim: int | None
    action_horizon: int | None
    max_token_len: int | None
    paligemma_variant: str | None
    action_expert_variant: str | None

    data_factory: str
    dataset_mode: str
    dataset_override_supported: bool
    default_repo_id: str | None
    default_asset_id: str | None
    asset_binding_mode: str
    asset_id_prefix: str
    required_features: tuple[str, ...]
    expected_state_dim: int | None
    expected_action_dim: int | None
    contract_source: str

    assets_dir: Path
    checkpoint_base_dir: Path

    weight_loader_class: str
    weight_path: str | None

    batch_size: int
    num_train_steps: int
    log_interval: int
    save_interval: int
    keep_period: int | None
    num_workers: int
    seed: int
    fsdp_devices: int
    wandb_enabled: bool
    ema_decay: float | None

    lr_schedule_type: str
    warmup_steps: int | None
    peak_lr: float | None
    decay_steps: int | None
    decay_lr: float | None

    optimizer_type: str
    clip_gradient_norm: float | None

    norm_stats_supported: bool
    runnable: bool
    runnable_reason: str
    inspect_warnings: tuple[str, ...] = ()
    config_tree: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ConfigInfo":
        model = payload.get("model", {})
        data = payload.get("data", {})
        train = payload.get("training", {})
        lr = payload.get("lr_schedule", {})
        opt = payload.get("optimizer", {})
        paths = payload.get("paths", {})
        weight = payload.get("weight_loader", {})
        contract = payload.get("dataset_contract", {})
        capabilities = payload.get("capabilities", {})

        return cls(
            name=str(payload.get("name", "")),
            project_name=str(payload.get("project_name", "openpi")),
            default_exp_name=str(payload.get("default_exp_name") or ""),
            model_type=str(model.get("model_type", "")),
            model_class=str(model.get("class", "")),
            pi05=bool(model.get("pi05", False)),
            action_dim=_maybe_int(model.get("action_dim")),
            action_horizon=_maybe_int(model.get("action_horizon")),
            max_token_len=_maybe_int(model.get("max_token_len")),
            paligemma_variant=_maybe_str(model.get("paligemma_variant")),
            action_expert_variant=_maybe_str(model.get("action_expert_variant")),
            data_factory=str(data.get("factory", "")),
            dataset_mode=str(data.get("dataset_mode", "unknown")),
            dataset_override_supported=bool(capabilities.get("dataset_override", False)),
            default_repo_id=_maybe_str(data.get("repo_id")),
            default_asset_id=_maybe_str(data.get("asset_id")),
            asset_binding_mode=str(data.get("asset_binding_mode", "none")),
            asset_id_prefix=str(data.get("asset_id_prefix", "")),
            required_features=tuple(str(x) for x in contract.get("required_features", []) if x),
            expected_state_dim=_maybe_int(contract.get("state_dim")),
            expected_action_dim=_maybe_int(contract.get("action_dim")),
            contract_source=str(contract.get("source", "unknown")),
            assets_dir=Path(str(paths.get("assets_dir", "./assets"))),
            checkpoint_base_dir=Path(str(paths.get("checkpoint_base_dir", "./checkpoints"))),
            weight_loader_class=str(weight.get("class", "")),
            weight_path=_maybe_str(weight.get("params_path")),
            batch_size=int(train.get("batch_size", 1)),
            num_train_steps=int(train.get("num_train_steps", 1)),
            log_interval=int(train.get("log_interval", 1)),
            save_interval=int(train.get("save_interval", 1)),
            keep_period=_maybe_int(train.get("keep_period")),
            num_workers=int(train.get("num_workers", 0)),
            seed=int(train.get("seed", 0)),
            fsdp_devices=int(train.get("fsdp_devices", 1)),
            wandb_enabled=bool(train.get("wandb_enabled", False)),
            ema_decay=_maybe_float(train.get("ema_decay")),
            lr_schedule_type=str(lr.get("type", "")),
            warmup_steps=_maybe_int(lr.get("warmup_steps")),
            peak_lr=_maybe_float(lr.get("peak_lr")),
            decay_steps=_maybe_int(lr.get("decay_steps")),
            decay_lr=_maybe_float(lr.get("decay_lr")),
            optimizer_type=str(opt.get("type", "")),
            clip_gradient_norm=_maybe_float(opt.get("clip_gradient_norm")),
            norm_stats_supported=bool(capabilities.get("norm_stats", False)),
            runnable=bool(capabilities.get("runnable", True)),
            runnable_reason=str(capabilities.get("runnable_reason", "")),
            inspect_warnings=tuple(str(x) for x in payload.get("inspect_warnings", []) if x),
            config_tree=payload.get("config_tree", {}) if isinstance(payload.get("config_tree", {}), dict) else {},
        )

    def asset_id_for_dataset(self, dataset_id: str | None) -> str | None:
        """Resolve the normalization asset id exactly from the config binding mode.

        No robot-specific rule is used here:
        - repo: asset id follows repo id
        - prefix: keep the configured parent and replace only the repo leaf
        - fixed: keep the explicit asset id unchanged
        - none: no asset id can be inferred
        """
        if self.asset_binding_mode == "fixed":
            return self.default_asset_id

        repo = dataset_id or self.default_repo_id
        if not repo:
            return self.default_asset_id

        if self.asset_binding_mode == "prefix" and self.asset_id_prefix:
            return str(PurePosixPath(self.asset_id_prefix) / repo)

        if self.asset_binding_mode in {"repo", "none"}:
            return repo

        return self.default_asset_id or repo

    def norm_stats_path(self, dataset_id: str | None) -> Path | None:
        if not self.norm_stats_supported:
            return None
        asset_id = self.asset_id_for_dataset(dataset_id)
        if not asset_id:
            return None
        return self.assets_dir / asset_id / "norm_stats.json"

    def checkpoint_dir(self, exp_name: str) -> Path:
        return self.checkpoint_base_dir / self.name / exp_name

    @property
    def model_label(self) -> str:
        base = self.model_type.upper() if self.model_type else self.model_class
        if self.pi05:
            base = "PI05"
        is_lora = any(
            (value or "").lower().endswith("_lora")
            for value in (self.paligemma_variant, self.action_expert_variant)
        )
        return f"{base} LoRA" if is_lora and "LoRA" not in base else base

    @property
    def initialization_label(self) -> str:
        if not self.weight_path:
            return self.weight_loader_class or "—"
        path = self.weight_path.rstrip("/")
        if "/checkpoints/" in path:
            tail = path.split("/checkpoints/", 1)[1].split("/", 1)[0]
            return tail.replace("_", " ")
        return path

    @property
    def data_label(self) -> str:
        if self.default_repo_id:
            return f"{self.data_factory} · {self.default_repo_id}"
        return self.data_factory or "—"


@dataclass(frozen=True)
class TrainSpec:
    config_name: str
    dataset_id: str | None
    exp_name: str
    num_train_steps: int
    batch_size: int
    save_interval: int
    log_interval: int
    keep_period: int | None
    num_workers: int
    peak_lr: float | None
    warmup_steps: int | None
    decay_steps: int | None
    decay_lr: float | None
    clip_gradient_norm: float | None
    seed: int
    fsdp_devices: int
    wandb_enabled: bool
    run_mode: RunMode

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "dataset_id": self.dataset_id,
            "exp_name": self.exp_name,
            "num_train_steps": self.num_train_steps,
            "batch_size": self.batch_size,
            "save_interval": self.save_interval,
            "log_interval": self.log_interval,
            "keep_period": self.keep_period,
            "num_workers": self.num_workers,
            "peak_lr": self.peak_lr,
            "warmup_steps": self.warmup_steps,
            "decay_steps": self.decay_steps,
            "decay_lr": self.decay_lr,
            "clip_gradient_norm": self.clip_gradient_norm,
            "seed": self.seed,
            "fsdp_devices": self.fsdp_devices,
            "wandb_enabled": self.wandb_enabled,
            "run_mode": self.run_mode.value,
        }


@dataclass(frozen=True)
class TrainingMetrics:
    step: int
    values: dict[str, float]


def _maybe_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _maybe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _maybe_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text and text != "None" else None
