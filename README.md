# Robot Learning Workbench

面向机器人学习与部署的开发基线，集成 OpenPI、CR3/O6 硬件适配、GELLO 遥操与数据采集、训练界面和部署界面。

## 快速开始

环境分开管理，避免 OpenPI 和 NRC 厂商 SDK 的 Python 版本、依赖互相影响：

| 用途 | 环境 | 启动方式 |
| --- | --- | --- |
| OpenPI 训练、模型服务 | `module/openpi/.venv`（Python 版本见 `module/openpi/.python-version`） | `scripts/run_openpi.sh` |
| NRC 客户端、Qt/GELLO 界面、硬件接口 | `module/nrc/.venv`（Python 3.12） | `scripts/run_nrc.sh` |

GELLO 的 LeRobot V2.1/V3 数据 Writer 使用独立 Python 3.12 环境，分别位于
`module/gello_writers/v21/.venv/`、`module/gello_writers/v3/.venv/`。
OpenPI 锁定的 LeRobot 不能替代官方 V2.1 Writer；不要混装两个 Writer 版本或改动训练环境。

Ubuntu 上首次部署：

```bash
./scripts/install_system_deps_ubuntu.sh
# 如尚未安装 uv：curl -LsSf https://astral.sh/uv/install.sh | sh
./scripts/setup_all_envs.sh
```

该脚本会创建/更新 OpenPI 和 NRC 两套主要 Python 环境，并检查依赖导入和版本约束。它需要预先安装 `uv`；NVIDIA 驱动、RealSense USB 规则/设备权限等系统和硬件条件需单独准备。GELLO 遥操依赖和独立 Writer 按下文 GELLO 说明单独安装。

## 启动界面

```bash
./scripts/run_hmi.sh          # 合并界面：训练标签页在前，部署标签页在后
./scripts/run_trainui.sh      # 仅训练界面
./scripts/run_deloy_hmi.sh    # 仅部署界面（脚本名保留现状）
```

训练界面从 OpenPI 注册表加载配置，可选择 `dataset/train/` 下的数据集、检查或计算归一化统计量并启动训练。W&B 默认关闭，可在高级设置中启用。训练结果保存在 `checkpoints/`。

部署界面可启动策略服务、选择训练结果、编排推理和轨迹回放任务。真实机器人运动前请确认硬件状态、工作空间和急停可用，并在界面中明确确认运动。

更多操作说明见 [HMI 指南](hmi/README.md) 和 [训练界面说明](hmi/trainui/README.md)。

## GELLO 遥操与数据采集

遥操界面、控制、设备适配和采集实现统一放在 `teleop/gello_cr/` 的职责子目录，SDK 复用父 `vendor/`。日常操作先看 [遥操快速开始](teleop/README.md)，源码边界见 [模块与父项目](docs/parent_workbench_framework.md)。

安装 NRC 环境中的界面/硬件依赖及独立 V2.1 Writer，再执行只读配置检查：

```bash
./scripts/setup_teleop_env.sh
./scripts/setup_gello_writer_env.sh v21
./scripts/run_teleop.sh --check-only
./scripts/run_teleop.sh
```

界面启动为 OFFLINE / IDLE，连接、使能和跟随均由人员明确操作。
硬件参数复用 `config/hardware/cr3_o6.toml`，GELLO 标定、动作库、任务和安全阈值位于
`config/teleop/gello_cr.json`。训练数据、恢复批次、命名轨迹分别位于 `dataset/train/`、
`dataset/staging/`、`dataset/replay/trajectories/`。

独立轨迹 CLI 入口为 `scripts/run_gello_replay.sh`，默认预览，真实回放需显式 `--execute`；
部署界面提供采集入口和共享轨迹任务。安装和运行脚本支持 `--help`。
完整安装、可选 V3 Writer、配置、预览和工作流格式见 [GELLO 集成说明](docs/gello_cr_integration.md)，详细维护指南见
[docs/teleop](docs/teleop/architecture.md)。运行和失败日志自动写入父 `logs/teleop.log`。无硬件窗口示例为 `teleop/gello_cr/examples/preview_collection.py`，
诊断工具为 `teleop/gello_cr/tools/workbench_diagnostics.py`，使用父 NRC 环境运行。真机联调尚未完成。

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
hmi/                 训练与部署桌面界面
module/openpi/       本项目维护的 OpenPI 源码
module/nrc/          NRC Python 环境目录（不提交虚拟环境）
module/gello_writers/ 独立的 V2.1/V3 数据 Writer 环境（不提交虚拟环境）
teleop/gello_cr/     遥操 UI、控制、设备适配、采集、工具和测试
vendor/              硬件与厂商接口适配
dataset/              本地训练、恢复批次和回放数据（不提交）
checkpoints/          模型检查点（不提交）
tasks/                可保存的任务流配置
scripts/              环境、验证和启动脚本
docs/teleop/          遥操架构、配置、数据、硬件和迁移指南
```

硬件参数集中在 `config/hardware/`，读取和校验入口是 `config/hardware.py`。新增机器人配置时复制对应 profile，避免在业务代码中散落 IP、端口和设备序列号。

## 开发约定

- 在 `module/openpi/` 内的修改属于本仓库；不会自动提交到 OpenPI 上游。
- 数据集、模型权重、虚拟环境和运行日志不进入 Git。
- 依赖按环境管理：OpenPI 依赖维护在 `module/openpi/`；NRC/界面基础依赖由 `scripts/setup_nrc_env.sh` 管理；GELLO 界面/硬件依赖和独立 Writer 分别由 `scripts/setup_teleop_env.sh`、`scripts/setup_gello_writer_env.sh` 管理。
- 提交前检查 `git status --short` 和 `git diff --check`。
