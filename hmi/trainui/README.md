# TrainUI v1.4

PySide6 training console for Robot Learning Workbench.

## Design rules

- All TrainUI Python/Qt code lives in `hmi/trainui/`.
- The user-facing launcher lives in `scripts/run_trainui.sh`.
- Qt runs in `module/nrc/.venv`.
- OpenPI inspection, normalization and training run through `scripts/run_openpi.sh` in `module/openpi/.venv`.
- OpenPI `scripts/train.py` is not copied or modified.
- TrainUI does **not** encode CR3, Piper, Aloha, DROID, Libero, camera names, or physical dimensions.

## v1.4: config-driven registry

TrainUI now reads every config registered in OpenPI's config registry. It does not filter by robot or by a hard-coded config name.

For each config it shows:

- model class / model type / PI05 flag
- model action dimension and horizon
- PaliGemma / action-expert variants when present
- DataConfigFactory type and repo id
- weight loader and checkpoint path
- optimizer and learning-rate schedule
- batch size, train steps, workers, seed, FSDP, W&B, EMA
- checkpoint/assets paths
- the complete registered TrainConfig dataclass tree
- a best-effort materialized DataConfig tree
- the dataset source keys derived from that config's RepackTransform

Use **完整配置** next to the config selector to inspect the entire config tree.

## Dataset validation

Dataset validation is derived from the selected config's RepackTransform. TrainUI no longer assumes three CR3 cameras or 12D state/action, and it does not assume Piper is 7D.

Dimensions are checked only when the selected DataConfig explicitly declares a dataset/physical dimension. Otherwise TrainUI displays the dimensions from `meta/info.json` without inventing an expected dimension.

## Dataset / asset binding

When the user selects another local dataset, the UI preserves the selected config's existing asset semantics:

- no explicit asset id: OpenPI follows repo id
- asset id equals repo id: follows the selected dataset
- asset id ends in `/<repo_id>`: preserves the prefix and changes only the repo leaf
- any other explicit asset id: treated as fixed and left unchanged

## Setup / launch

```bash
./scripts/setup_nrc_env.sh
./scripts/setup_openpi_env.sh
./scripts/run_trainui.sh
```

## Tests

```bash
PYTHONPATH=. python -m pytest hmi/trainui/tests -q
```

## v1.5 数据源预检

TrainUI 会区分三类 LeRobot 数据源：本地已验证数据集、配置声明的远程/外部 repo、以及配置声明但本地缺失的简单 repo_id。对于最后一种情况，UI 会阻止归一化统计和训练启动，避免 OpenPI 在本地缺失后继续把该简单名称当作 Hugging Face repo_id 并产生误导性的 404。

本地数据集必须包含 `dataset/train/<repo_id>/meta/info.json`。对于带命名空间的本地布局（如 `dataset/train/org/name/meta/info.json`）也会递归发现。

## v1.6 配置按需加载

TrainUI 不再在启动时对 OpenPI 注册表中的每个 TrainConfig 执行完整解析。
启动时只读取配置名称；用户选择某个配置后，持久化 inspector 进程才对该配置执行
DataConfig.create、RepackTransform 推导和完整配置树序列化。inspector 进程在 UI 生命周期内
保持运行，因此切换配置不需要反复启动 Python/JAX 环境。`--all` 仅保留为诊断命令，UI 不调用。
