from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from hmi.trainui.models import ConfigInfo, DatasetInfo
from hmi.trainui.paths import DATASET_ROOT


def _feature_last_dim(feature: Any) -> int | None:
    if not isinstance(feature, dict):
        return None
    shape = feature.get("shape")
    if not isinstance(shape, list) or not shape:
        return None
    last = shape[-1]
    return int(last) if isinstance(last, int) and not isinstance(last, bool) else None


def _looks_remote_repo_id(repo_id: str) -> bool:
    """Return True for repository-like ids such as org/dataset.

    A single local workbench dataset is normally stored as
    dataset/train/<name>.  Hugging Face repositories normally have a namespace
    and therefore contain '/'.  This is deliberately only a UI preflight
    heuristic: OpenPI remains the final authority when a remote source is used.
    """
    if "://" in repo_id:
        return True
    path = PurePosixPath(repo_id)
    return not path.is_absolute() and len(path.parts) >= 2 and ".." not in path.parts


class DatasetService:
    """Inspect datasets against the selected OpenPI TrainConfig.

    Validation is config-driven. Required source keys come from the selected
    config's RepackTransform.  TrainUI never assumes a robot name.

    Local datasets are discovered recursively so namespaced repository layouts
    such as ``org/dataset/meta/info.json`` are also supported.
    """

    def __init__(self, dataset_root: Path = DATASET_ROOT):
        self.dataset_root = dataset_root

    def discover(self, config: ConfigInfo) -> list[DatasetInfo]:
        if not config.dataset_override_supported or not self.dataset_root.is_dir():
            return []

        datasets: list[DatasetInfo] = []
        seen: set[str] = set()
        for info_file in sorted(self.dataset_root.rglob("meta/info.json")):
            path = info_file.parent.parent
            try:
                repo_id = path.relative_to(self.dataset_root).as_posix()
            except ValueError:
                continue
            if not repo_id or repo_id in seen:
                continue
            seen.add(repo_id)
            datasets.append(self._read_dataset(path, config, repo_id=repo_id))
        return datasets

    def configured_source(self, config: ConfigInfo) -> DatasetInfo | None:
        """Represent the repo_id declared by the selected config.

        If the configured repo exists under ``dataset/train`` it is treated as
        a normal local dataset.  If it looks like a namespaced remote repo it is
        allowed but marked unverified.  A simple local-style id that is missing
        is marked invalid so TrainUI does not blindly call OpenPI, which would
        otherwise fall back to Hugging Face and typically produce a confusing
        404.
        """
        repo_id = config.default_repo_id
        if not repo_id:
            return None

        path = self.dataset_root / Path(*PurePosixPath(repo_id).parts)
        info_file = path / "meta" / "info.json"
        if info_file.is_file():
            return self._read_dataset(path, config, repo_id=repo_id)

        if _looks_remote_repo_id(repo_id):
            return DatasetInfo(
                repo_id=repo_id,
                path=path,
                total_episodes=None,
                total_frames=None,
                fps=None,
                state_dim=None,
                action_dim=None,
                features=(),
                valid=True,
                errors=(),
                warnings=(
                    "该 repo_id 来自当前 OpenPI 配置，本地未找到 meta/info.json；"
                    "TrainUI 将其视为远程/外部数据源，最终可用性由 OpenPI 校验。",
                ),
                source="config-remote",
            )

        return DatasetInfo(
            repo_id=repo_id,
            path=path,
            total_episodes=None,
            total_frames=None,
            fps=None,
            state_dim=None,
            action_dim=None,
            features=(),
            valid=False,
            errors=(
                f"配置指定的数据集 '{repo_id}' 未在本地找到：{info_file}",
                "这是一个不含命名空间的 repo_id。若本意是本地数据集，请把数据放到上述目录，"
                "或在下拉框选择实际存在的数据集；若本意是 Hugging Face 数据集，请在 config.py 中使用完整的 namespace/repo_id。",
            ),
            warnings=(
                "OpenPI 在本地找不到该数据集后会尝试按 Hugging Face repo_id 解析；"
                "对这种简单名称通常会得到 RepositoryNotFoundError/404。",
            ),
            source="config-missing",
        )

    def _read_dataset(self, path: Path, config: ConfigInfo, *, repo_id: str | None = None) -> DatasetInfo:
        errors: list[str] = []
        warnings: list[str] = []
        info_file = path / "meta" / "info.json"
        resolved_repo_id = repo_id or path.name

        try:
            data = json.loads(info_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return DatasetInfo(
                repo_id=resolved_repo_id,
                path=path,
                total_episodes=None,
                total_frames=None,
                fps=None,
                state_dim=None,
                action_dim=None,
                features=(),
                valid=False,
                errors=(f"无法读取 meta/info.json: {exc}",),
            )

        raw_features = data.get("features")
        features = raw_features if isinstance(raw_features, dict) else {}
        feature_names = tuple(sorted(str(key) for key in features))

        if config.required_features:
            for required in config.required_features:
                if required not in features:
                    errors.append(f"缺少字段: {required}")
        else:
            warnings.append(
                "当前配置没有可静态推导的 RepackTransform 字段要求；"
                "TrainUI 仅展示数据集元信息，最终兼容性由 OpenPI 数据管线校验。"
            )

        state_dim = _feature_last_dim(features.get("observation.state"))
        if state_dim is None:
            for key in config.required_features:
                if "state" in key.lower() and key in features:
                    state_dim = _feature_last_dim(features.get(key))
                    if state_dim is not None:
                        break

        action_dim = _feature_last_dim(features.get("action"))
        if action_dim is None:
            for key in config.required_features:
                lower = key.lower()
                if ("action" in lower or lower.endswith("actions")) and key in features:
                    action_dim = _feature_last_dim(features.get(key))
                    if action_dim is not None:
                        break

        if config.expected_state_dim is not None and state_dim is not None:
            if state_dim != config.expected_state_dim:
                errors.append(
                    f"状态维度为 {state_dim}，当前配置声明要求 {config.expected_state_dim}"
                )

        if config.expected_action_dim is not None and action_dim is not None:
            if action_dim != config.expected_action_dim:
                errors.append(
                    f"动作维度为 {action_dim}，当前配置声明要求 {config.expected_action_dim}"
                )

        if config.contract_source:
            warnings.append(f"字段要求来源: {config.contract_source}")

        def maybe_int(key: str) -> int | None:
            value = data.get(key)
            return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

        fps_raw = data.get("fps")
        fps = (
            float(fps_raw)
            if isinstance(fps_raw, (int, float)) and not isinstance(fps_raw, bool)
            else None
        )

        return DatasetInfo(
            repo_id=resolved_repo_id,
            path=path,
            total_episodes=maybe_int("total_episodes"),
            total_frames=maybe_int("total_frames"),
            fps=fps,
            state_dim=state_dim,
            action_dim=action_dim,
            features=feature_names,
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
            source="local",
        )
