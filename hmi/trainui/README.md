# 训练界面

TrainUI 是 OpenPI 训练的图形入口，复用 OpenPI 注册的 `TrainConfig`，不另建一套模型配置。界面支持数据集检查、归一化统计、训练启动和训练状态监控。

## 环境与启动

TrainUI 使用 NRC 环境运行 PySide6，训练任务则在独立的 OpenPI 环境中执行：

```text
module/nrc/.venv      Qt 界面
module/openpi/.venv   OpenPI、JAX、LeRobot 和训练进程
```

首次安装：

```bash
./scripts/bootstrap.sh
./scripts/setup_nrc_env.sh
```

启动训练界面：

```bash
./scripts/run_trainui.sh
```

也可以通过合并界面的“训练”标签页使用：

```bash
./scripts/run_hmi.sh
```

## 使用流程

1. 选择 OpenPI 训练配置和本地数据集。
2. 检查数据要求，并按需计算归一化统计量。
3. 设置实验名和训练参数，启动训练。
4. 在界面查看日志、进度、损失、GPU 状态和 checkpoint。

W&B 默认关闭；如需使用，可在界面的高级设置中启用，并按 W&B 提示配置账号。

本地 LeRobot 数据集默认放在 `dataset/train/<数据集名>/`，其中应有 `meta/info.json` 等 LeRobot 元数据。检查点保存在 `checkpoints/`，数据和检查点不会由 Git 跟踪。

命令行训练示例：

```bash
./scripts/run_openpi.sh scripts/train.py \
  pi05_cr3_o6_lora --exp-name=<实验名>
```

## 代码位置

- 界面：`hmi/trainui/views/`
- 训练流程控制：`hmi/trainui/controller.py`
- OpenPI 子进程封装：`hmi/trainui/services/openpi_service.py`
- 配置与训练桥接：`hmi/trainui/bridge/`
- OpenPI 配置真源：`module/openpi/src/openpi/training/config.py`

运行测试：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  module/openpi/.venv/bin/python -m pytest hmi/trainui/tests -q
```
