# 桌面界面

本项目提供训练、部署和遥操采集 PySide6 界面。首次使用先创建 OpenPI 与 NRC 环境：

```bash
./scripts/bootstrap.sh
./scripts/setup_nrc_env.sh
```

启动方式：

```bash
./scripts/run_hmi.sh          # 合并界面：训练页在前，部署页在后
./scripts/run_trainui.sh      # 仅训练
./scripts/run_deloy_hmi.sh    # 仅部署
```

## 训练

训练页读取 OpenPI 中已注册的配置，使用 `dataset/train/` 下的 LeRobot 数据集。可检查数据、计算归一化统计量、配置训练参数并查看训练进度。W&B 默认关闭，需要时可在高级设置中开启。

详细说明见 [TrainUI 指南](trainui/README.md)。

## 部署

部署页可选择硬件 profile、策略配置和 checkpoint，管理模型服务，并编排策略推理、数据集回放及走点轨迹任务。任务流可保存到 `tasks/`。

硬件运动有风险：确认机器人及工作区域安全后再执行，并确保现场人员能够使用实体急停。程序检测到控制器错误状态时会停止后续任务；请先排查并复位故障，不要绕过保护。

## 遥操与数据采集

`collection/` 为父级遥操与数据采集控制台；`deploy/` 保留部署与任务工作流控制台，`trainui/` 提供训练界面。
按 [GELLO 集成说明](../docs/gello_cr_integration.md) 安装遥操依赖和独立 Writer 后启动：

```bash
./scripts/run_teleop.sh
```

采集界面布局由 `collection/forms/` 的 Qt Designer `.ui` 维护，修改后从仓库根目录运行：

```bash
module/nrc/.venv/bin/python scripts/generate_collection_ui.py
```

共享状态机、运行时和 Recorder 位于 `core/workbench`，设备管理位于 `core/hardware`；共享架构见
[父级框架](../docs/parent_workbench_framework.md) 和 [详细指南](../docs/teleop/architecture.md)。

无硬件窗口预览使用 NRC 环境运行：

```bash
./scripts/run_nrc.sh python examples/preview_collection.py
```
