# 桌面界面

此目录提供训练和部署两个 PySide6 界面。首次使用先创建 OpenPI 与 NRC 环境：

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

遥操和采集界面位于 `teleop/gello_cr/ui/`，安装与操作见 [遥操快速开始](../teleop/README.md)。

```bash
./scripts/run_teleop.sh
```

布局由 `teleop/gello_cr/ui/forms/` 的 Qt Designer `.ui` 维护，修改后从仓库根目录运行
`module/nrc/.venv/bin/python scripts/generate_collection_ui.py`。无硬件预览见
[离线示例](../teleop/gello_cr/examples/README.md)。

任务启动和执行失败的上下文自动保存到父项目 `logs/teleop.log`。
