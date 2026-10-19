# Robot Learning Workbench

面向机器人学习与部署的开发基线，集成 OpenPI、CR3/O6 硬件适配、训练界面和部署界面。

## 快速开始

环境分开管理，避免 OpenPI 和 NRC 厂商 SDK 的 Python 版本、依赖互相影响：

| 用途 | 环境 | 启动方式 |
| --- | --- | --- |
| OpenPI 训练、模型服务 | `module/openpi/.venv`（Python 版本见 `module/openpi/.python-version`） | `scripts/run_openpi.sh` |
| NRC 客户端、Qt 界面、硬件接口 | `module/nrc/.venv`（Python 3.12） | `scripts/run_nrc.sh` |

Ubuntu 上首次部署：

```bash
./scripts/install_system_deps_ubuntu.sh
# 如尚未安装 uv：curl -LsSf https://astral.sh/uv/install.sh | sh
./scripts/setup_all_envs.sh
```

该脚本会创建/更新两套 Python 环境，并检查依赖导入和版本约束。它需要预先安装 `uv`；NVIDIA 驱动、RealSense USB 规则/设备权限等系统和硬件条件需单独准备。

## 启动界面

```bash
./scripts/run_hmi.sh          # 合并界面：训练标签页在前，部署标签页在后
./scripts/run_trainui.sh      # 仅训练界面
./scripts/run_deloy_hmi.sh    # 仅部署界面（脚本名保留现状）
```

训练界面从 OpenPI 注册表加载配置，可选择 `dataset/train/` 下的数据集、检查或计算归一化统计量并启动训练。W&B 默认关闭，可在高级设置中启用。训练结果保存在 `checkpoints/`。

部署界面可启动策略服务、选择训练结果、编排推理和轨迹回放任务。真实机器人运动前请确认硬件状态、工作空间和急停可用，并在界面中明确确认运动。

更多操作说明见 [HMI 指南](hmi/README.md) 和 [训练界面说明](hmi/trainui/README.md)。

## 命令行常用操作

训练：

```bash
./scripts/run_openpi.sh scripts/train.py \
  pi05_cr3_o6_lora --exp-name=<实验名>
```

使用硬件测试前确认机器人周围安全。NRC 接口测试通过 Python 3.12 环境运行：

```bash
./scripts/run_nrc.sh python test/test_nrc_interface.py
```

OpenPI、LeRobot 和 GPU 环境检查：

```bash
./scripts/verify_openpi_env.sh
```

## 项目布局

```text
config/hardware/     硬件 profile（机器人、相机和手）
core/openpi/         OpenPI 训练外的部署与回放业务
hmi/                 训练、部署桌面界面
module/openpi/       本项目维护的 OpenPI 源码
module/nrc/          NRC Python 环境目录（不提交虚拟环境）
vendor/              硬件与厂商接口适配
dataset/              本地训练和回放数据（不提交）
checkpoints/          模型检查点（不提交）
tasks/                可保存的任务流配置
scripts/              环境、验证和启动脚本
```

硬件参数集中在 `config/hardware/`，读取和校验入口是 `config/hardware.py`。新增机器人配置时复制对应 profile，避免在业务代码中散落 IP、端口和设备序列号。

## 开发约定

- 在 `module/openpi/` 内的修改属于本仓库；不会自动提交到 OpenPI 上游。
- 数据集、模型权重、虚拟环境和运行日志不进入 Git。
- 依赖按环境管理：OpenPI 依赖维护在 `module/openpi/`；NRC/界面基础依赖由 `scripts/setup_nrc_env.sh` 管理。
- 提交前检查 `git status --short` 和 `git diff --check`。
