from __future__ import annotations

import argparse
import dataclasses
import enum
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from openpi.training import config as training_config


_INSPECT_ASSET_ROOT = Path("/tmp/robot_learning_workbench_trainui_inspect_no_assets")


def _class_name(value: Any) -> str:
    return type(value).__name__


def _qualified_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _plain_string(value: Any) -> str | None:
    # tyro.MISSING and other sentinels must not become fake repo ids in the UI.
    return value if isinstance(value, str) and value else None


def _safe_tree(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> Any:
    """Convert arbitrary config objects into JSON-safe data for the details dialog.

    This intentionally serializes dataclass *fields*, not properties.  That keeps
    config inspection read-only and avoids triggering expensive model/data work.
    """
    if seen is None:
        seen = set()

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if depth >= 10:
        return f"<{_qualified_name(value)}>"

    obj_id = id(value)
    if obj_id in seen:
        return f"<循环引用: {_qualified_name(value)}>"

    if dataclasses.is_dataclass(value):
        seen.add(obj_id)
        result: dict[str, Any] = {"__class__": _qualified_name(value)}
        for field in dataclasses.fields(value):
            try:
                child = getattr(value, field.name)
            except Exception as exc:  # pragma: no cover - defensive introspection
                result[field.name] = f"<读取失败: {exc}>"
                continue
            result[field.name] = _safe_tree(child, depth=depth + 1, seen=seen)
        seen.remove(obj_id)
        return result

    if isinstance(value, dict):
        seen.add(obj_id)
        result = {
            str(key): _safe_tree(child, depth=depth + 1, seen=seen)
            for key, child in value.items()
        }
        seen.remove(obj_id)
        return result

    if isinstance(value, (list, tuple, set, frozenset)):
        seen.add(obj_id)
        result = [_safe_tree(child, depth=depth + 1, seen=seen) for child in value]
        seen.remove(obj_id)
        return result

    if callable(value):
        module = getattr(value, "__module__", "")
        qualname = getattr(value, "__qualname__", getattr(value, "__name__", repr(value)))
        return f"{module}.{qualname}" if module else str(qualname)

    try:
        text = repr(value)
    except Exception:  # pragma: no cover
        text = f"<{_qualified_name(value)}>"
    return text if len(text) <= 2000 else text[:1997] + "..."


def _dataclass_field_names(value: Any) -> set[str]:
    if not dataclasses.is_dataclass(value):
        return set()
    return {field.name for field in dataclasses.fields(value)}


def _safe_create_data_config(config: Any) -> tuple[Any | None, str | None]:
    """Best-effort materialization of DataConfig without downloading assets.

    DataConfigFactory.create() is useful because several official configs build
    their RepackTransform inside create(), not as a dataclass field.  To keep
    inspection side-effect-free, redirect normalization asset lookup to a known
    missing local directory.  create() should only construct transforms; it does
    not load the dataset itself.
    """
    factory = config.data
    try:
        safe_factory = factory
        fields = _dataclass_field_names(factory)
        if "assets" in fields:
            assets = getattr(factory, "assets", None)
            if dataclasses.is_dataclass(assets) and "assets_dir" in _dataclass_field_names(assets):
                safe_assets = dataclasses.replace(assets, assets_dir=str(_INSPECT_ASSET_ROOT))
                safe_factory = dataclasses.replace(factory, assets=safe_assets)
        return safe_factory.create(_INSPECT_ASSET_ROOT / config.name, config.model), None
    except Exception as exc:
        return None, f"DataConfig 解析失败（仅影响 UI 自动推导，不影响原配置注册）：{exc}"


def _walk_objects(value: Any, *, max_depth: int = 8) -> Iterable[Any]:
    seen: set[int] = set()

    def walk(node: Any, depth: int):
        if node is None or depth > max_depth:
            return
        if isinstance(node, (str, int, float, bool, bytes, Path, enum.Enum)):
            return
        obj_id = id(node)
        if obj_id in seen:
            return
        seen.add(obj_id)
        yield node

        if dataclasses.is_dataclass(node):
            for field in dataclasses.fields(node):
                try:
                    child = getattr(node, field.name)
                except Exception:
                    continue
                yield from walk(child, depth + 1)
        elif isinstance(node, dict):
            for child in node.values():
                yield from walk(child, depth + 1)
        elif isinstance(node, (list, tuple, set, frozenset)):
            for child in node:
                yield from walk(child, depth + 1)

    yield from walk(value, 0)


def _leaf_strings(tree: Any) -> list[str]:
    result: list[str] = []
    if isinstance(tree, str):
        result.append(tree)
    elif isinstance(tree, dict):
        for value in tree.values():
            result.extend(_leaf_strings(value))
    elif isinstance(tree, (list, tuple)):
        for value in tree:
            result.extend(_leaf_strings(value))
    return result


def _required_dataset_features(factory: Any, data_config: Any | None) -> tuple[list[str], str]:
    """Derive dataset source keys from RepackTransform.structure.

    No robot name, camera name or physical dimension is encoded in TrainUI.
    The source keys come directly from the selected config's transforms.
    """
    sources: list[str] = []
    roots = [factory]
    if data_config is not None:
        roots.append(data_config)

    prompt_is_generated = False
    if data_config is not None:
        prompt_is_generated = bool(getattr(data_config, "prompt_from_task", False))
        for obj in _walk_objects(data_config):
            if _class_name(obj) == "InjectDefaultPrompt" and getattr(obj, "prompt", None) is not None:
                prompt_is_generated = True

    found_repack = False
    for root in roots:
        for obj in _walk_objects(root):
            if _class_name(obj) != "RepackTransform" or not hasattr(obj, "structure"):
                continue
            found_repack = True
            sources.extend(_leaf_strings(getattr(obj, "structure")))

    if data_config is not None:
        action_keys = getattr(data_config, "action_sequence_keys", ()) or ()
        if isinstance(action_keys, str):
            action_keys = (action_keys,)
        sources.extend(str(key) for key in action_keys if isinstance(key, str))

    deduped: list[str] = []
    for source in sources:
        if not source:
            continue
        if source == "prompt" and prompt_is_generated:
            continue
        if source not in deduped:
            deduped.append(source)

    if found_repack:
        return deduped, "RepackTransform"
    if deduped:
        return deduped, "action_sequence_keys"
    return [], "无法从配置自动推导"


def _declared_dimension(factory: Any, data_config: Any | None, kind: str) -> int | None:
    candidates = (
        f"physical_{kind}_dim",
        f"dataset_{kind}_dim",
        f"{kind}_dim",
    )
    for owner in (factory, data_config):
        if owner is None:
            continue
        for name in candidates:
            value = getattr(owner, name, None)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                return value
    return None


def _asset_binding(repo_id: str | None, asset_id: str | None) -> tuple[str, str]:
    if asset_id is None:
        return "repo", ""
    if repo_id and asset_id == repo_id:
        return "repo", ""
    if repo_id:
        suffix = "/" + repo_id
        if asset_id.endswith(suffix):
            parent = str(PurePosixPath(asset_id).parent)
            return "prefix", "" if parent == "." else parent
    return "fixed", ""


def _dataset_mode(factory: Any, data_config: Any | None) -> str:
    name = _class_name(factory)
    if name == "FakeDataConfig":
        return "fake"
    if "RLDS" in name:
        return "rlds"
    if data_config is not None and getattr(data_config, "rlds_data_dir", None):
        return "rlds"
    return "lerobot" if "repo_id" in _dataclass_field_names(factory) else "config"


def _serialize(config: Any) -> dict[str, Any]:
    warnings: list[str] = []
    factory = config.data
    data_config, data_error = _safe_create_data_config(config)
    if data_error:
        warnings.append(data_error)

    model = config.model
    lr = config.lr_schedule
    optimizer = config.optimizer
    loader = config.weight_loader

    repo_id = _plain_string(getattr(factory, "repo_id", None))
    assets = getattr(factory, "assets", None)
    asset_id = _plain_string(getattr(assets, "asset_id", None)) if assets is not None else None
    binding_mode, asset_prefix = _asset_binding(repo_id, asset_id)

    required_features, contract_source = _required_dataset_features(factory, data_config)
    expected_state_dim = _declared_dimension(factory, data_config, "state")
    expected_action_dim = _declared_dimension(factory, data_config, "action")

    dataset_mode = _dataset_mode(factory, data_config)
    data_fields = _dataclass_field_names(factory)
    dataset_override = (
        dataset_mode == "lerobot"
        and dataclasses.is_dataclass(factory)
        and "repo_id" in data_fields
    )

    default_exp_name = _plain_string(getattr(config, "exp_name", None)) or ""

    config_tree = {
        "注册的 TrainConfig": _safe_tree(config),
        "解析后的 DataConfig": (
            _safe_tree(data_config) if data_config is not None else {"error": data_error or "不可用"}
        ),
        "TrainUI 自动推导": {
            "dataset_mode": dataset_mode,
            "dataset_override_supported": dataset_override,
            "required_dataset_features": required_features,
            "dataset_contract_source": contract_source,
            "expected_state_dim": expected_state_dim,
            "expected_action_dim": expected_action_dim,
            "asset_binding_mode": binding_mode,
            "asset_id_prefix": asset_prefix,
        },
    }

    return {
        "name": config.name,
        "project_name": str(getattr(config, "project_name", "openpi")),
        "default_exp_name": default_exp_name,
        "model": {
            "class": _class_name(model),
            "model_type": _enum_value(getattr(model, "model_type", "")),
            "pi05": bool(getattr(model, "pi05", False)),
            "action_dim": getattr(model, "action_dim", None),
            "action_horizon": getattr(model, "action_horizon", None),
            "max_token_len": getattr(model, "max_token_len", None),
            "paligemma_variant": getattr(model, "paligemma_variant", None),
            "action_expert_variant": getattr(model, "action_expert_variant", None),
        },
        "data": {
            "factory": _class_name(factory),
            "dataset_mode": dataset_mode,
            "repo_id": repo_id,
            "asset_id": asset_id,
            "asset_binding_mode": binding_mode,
            "asset_id_prefix": asset_prefix,
        },
        "paths": {
            "assets_dir": str(config.assets_dirs),
            "checkpoint_base_dir": str(config.checkpoint_base_dir),
        },
        "training": {
            "batch_size": config.batch_size,
            "num_train_steps": config.num_train_steps,
            "log_interval": config.log_interval,
            "save_interval": config.save_interval,
            "keep_period": config.keep_period,
            "num_workers": config.num_workers,
            "seed": config.seed,
            "fsdp_devices": config.fsdp_devices,
            "wandb_enabled": config.wandb_enabled,
            "ema_decay": config.ema_decay,
        },
        "lr_schedule": {
            "type": _class_name(lr),
            "warmup_steps": getattr(lr, "warmup_steps", None),
            "peak_lr": getattr(lr, "peak_lr", None),
            "decay_steps": getattr(lr, "decay_steps", None),
            "decay_lr": getattr(lr, "decay_lr", None),
        },
        "optimizer": {
            "type": _class_name(optimizer),
            "clip_gradient_norm": getattr(optimizer, "clip_gradient_norm", None),
        },
        "weight_loader": {
            "class": _class_name(loader),
            "params_path": (
                str(getattr(loader, "params_path"))
                if getattr(loader, "params_path", None) is not None
                else None
            ),
        },
        "dataset_contract": {
            "required_features": required_features,
            "state_dim": expected_state_dim,
            "action_dim": expected_action_dim,
            "source": contract_source,
        },
        "capabilities": {
            "dataset_override": dataset_override,
            "norm_stats": dataset_mode == "lerobot" and dataset_override,
            "runnable": True,
            "runnable_reason": "",
        },
        "inspect_warnings": warnings,
        "config_tree": config_tree,
    }


def _registry() -> list[tuple[str, Any]]:
    registry = getattr(training_config, "_CONFIGS_DICT", None)
    if isinstance(registry, dict):
        return list(registry.items())

    configs = getattr(training_config, "_CONFIGS", None)
    if configs is not None:
        return [(cfg.name, cfg) for cfg in configs]

    raise RuntimeError("当前 OpenPI config 模块没有可读取的配置注册表")


def all_configs() -> list[dict[str, Any]]:
    """Compatibility/debug path: fully inspect every registered config.

    TrainUI itself intentionally does NOT call this path anymore.  It exists for
    diagnostics and for users who explicitly request a complete registry dump.
    """
    result: list[dict[str, Any]] = []
    for name, cfg in _registry():
        try:
            result.append(_serialize(cfg))
        except Exception as exc:  # keep one bad inspector from hiding the registry
            result.append(
                {
                    "name": name,
                    "project_name": "openpi",
                    "default_exp_name": "",
                    "model": {},
                    "data": {"factory": _class_name(getattr(cfg, "data", object())), "dataset_mode": "unknown"},
                    "paths": {
                        "assets_dir": str(getattr(cfg, "assets_dirs", "./assets")),
                        "checkpoint_base_dir": str(getattr(cfg, "checkpoint_base_dir", "./checkpoints")),
                    },
                    "training": {
                        "batch_size": getattr(cfg, "batch_size", 1),
                        "num_train_steps": getattr(cfg, "num_train_steps", 1),
                        "log_interval": getattr(cfg, "log_interval", 1),
                        "save_interval": getattr(cfg, "save_interval", 1),
                        "keep_period": getattr(cfg, "keep_period", None),
                        "num_workers": getattr(cfg, "num_workers", 0),
                        "seed": getattr(cfg, "seed", 0),
                        "fsdp_devices": getattr(cfg, "fsdp_devices", 1),
                        "wandb_enabled": getattr(cfg, "wandb_enabled", False),
                        "ema_decay": getattr(cfg, "ema_decay", None),
                    },
                    "lr_schedule": {"type": _class_name(getattr(cfg, "lr_schedule", object()))},
                    "optimizer": {"type": _class_name(getattr(cfg, "optimizer", object()))},
                    "weight_loader": {"class": _class_name(getattr(cfg, "weight_loader", object()))},
                    "dataset_contract": {
                        "required_features": [],
                        "state_dim": None,
                        "action_dim": None,
                        "source": "解析失败",
                    },
                    "capabilities": {
                        "dataset_override": False,
                        "norm_stats": False,
                        "runnable": True,
                        "runnable_reason": "配置存在，但 TrainUI 详细解析失败；训练仍交给 OpenPI 本身。",
                    },
                    "inspect_warnings": [f"配置 {name} 详细解析失败: {exc}"],
                    "config_tree": {"注册的 TrainConfig": _safe_tree(cfg), "TrainUI 解析错误": str(exc)},
                }
            )
    return result


def config_names() -> list[str]:
    """Read only registry names; never create/serialize each DataConfig."""
    return [name for name, _cfg in _registry()]


def _server() -> int:
    """Persistent lightweight inspector used by TrainUI.

    OpenPI's config module is imported exactly once by this process.  The server
    first sends only the registry names.  Detailed materialization (_serialize,
    including DataConfig.create()) happens only for the config currently selected
    by the user.
    """
    names = config_names()
    print("TRAINUI_NAMES=" + json.dumps(names, ensure_ascii=False), flush=True)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request_name = ""
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("请求必须是 JSON object")
            command = str(request.get("cmd", ""))

            if command == "inspect":
                request_name = str(request.get("name", ""))
                if not request_name:
                    raise ValueError("缺少配置名称")
                payload = _serialize(training_config.get_config(request_name))
                print("TRAINUI_CONFIG=" + json.dumps(payload, ensure_ascii=False), flush=True)
                continue

            if command == "names":
                print("TRAINUI_NAMES=" + json.dumps(names, ensure_ascii=False), flush=True)
                continue

            if command == "quit":
                return 0

            raise ValueError(f"未知命令: {command}")
        except Exception as exc:
            error = {"name": request_name, "message": str(exc)}
            print("TRAINUI_ERROR=" + json.dumps(error, ensure_ascii=False), flush=True)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true", help="TrainUI 持久化按需配置检查服务")
    parser.add_argument("--names", action="store_true", help="仅列出配置名称，不解析详细配置")
    parser.add_argument("--all", action="store_true", help="诊断用途：详细读取全部注册配置")
    # Backward-compatible alias used by TrainUI <= 1.3.
    parser.add_argument("--all-compatible", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--config-name")
    args = parser.parse_args()

    if args.server:
        raise SystemExit(_server())

    if args.names:
        payload: Any = config_names()
    elif args.all or args.all_compatible:
        payload = all_configs()
    elif args.config_name:
        payload = _serialize(training_config.get_config(args.config_name))
    else:
        parser.error("use --server, --names, --all or --config-name")

    print("TRAINUI_JSON=" + json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
