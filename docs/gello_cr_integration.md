# GELLO 遥操与父工作台集成

父项目正式入口是 `scripts/run_teleop.sh`，运行 `python -m teleop.gello_cr.ui`。
启动界面处于 OFFLINE / IDLE；连接机器人、使能、启动跟随、相机和采集均需人工操作。
`--check-only` 仅加载并校验配置，不连接设备。遥操的界面、运行时、控制、采集和设备适配均位于 `teleop/gello_cr/` 的职责子目录；
SDK 复用父 `vendor/`，配置、数据和日志使用父项目目录。日常操作见
[遥操快速开始](../teleop/README.md)，详细指南位于 [docs/teleop](teleop/architecture.md)。

## 配置与共享 SDK

`config/teleop/gello_cr.json` 是集成后的遥操配置，保留来源项目的 GELLO 关节标定、
方向、倍率、HOME/A/B/C/D preset、O6 动作库、任务描述、采样质量和运动安全阈值。
这些值是迁移数据，首次真机使用前仍须由现场负责人复核，不能把已有 preset 当作现场已验收位置。

`workbench.hardware_config` 默认指向 `../hardware/cr3_o6.toml`。硬件 TOML 统一拥有
NRC 地址/端口/连接参数、七轴 ServoJ 限制、O6 物理端口及三台相机参数。
组合配置在加载时从 TOML 生成相机槽位和输出尺寸；设置页显示来源并将这些共享字段设为只读。
保存 GELLO 标定或采集设置不改写硬件 TOML。
临时切换工位使用 `--hardware-config`，切换遥操 JSON 使用 `--config`：

```bash
./scripts/run_teleop.sh --check-only
./scripts/run_teleop.sh --hardware-config config/hardware/cr3_o6_lab_b.toml --check-only
./scripts/run_teleop.sh --config /absolute/path/gello_cr.local.json --check-only
```

配置内部的相对路径均相对 JSON 所在目录解析，命令行路径相对脚本运行时的仓库根目录解析。
脚本可从任意当前目录通过绝对路径调用，且统一切换到仓库根目录。
复制 JSON 到其他目录时，应同时调整其中的相对路径。

SDK 只维护在父仓库：NRC 为 `vendor/nrc_interface/nrc_linux_x86_64/`，
O6 为 `vendor/actuator/linkerhand-python-sdk/LinkerHand/`，GELLO 为 `vendor/gello/`。
JSON 中对应路径使用 `../../vendor/...`，不依赖嵌套模块的 SDK 副本。
GELLO 采样接口保留成功总线读数的 monotonic 时间戳，重复读取缓存不会刷新采样时刻。

## 安装与环境边界

界面及硬件适配使用兼容的 Python 3.12，独立环境位于 `module/nrc/.venv/`。
`run_teleop.sh` 和 `run_gello_replay.sh` 委托 `run_nrc.sh` 检查 Python ABI 并补充
`LD_LIBRARY_PATH` 中的 Python 共享库目录。解释器优先级是
`GELLO_CR_PYTHON`、`NRC_PYTHON`、显式 `NRC_ENV/bin/python`、兼容的已激活 Conda、默认 NRC 环境。
自动复用 Conda 前检查 CPython 3.12、NumPy `>=1.26,<2`、基础界面依赖、
O6 的 `pymodbus==3.5.1` 和 D435 的 `pyrealsense2`；只导入库，不连接设备。
不兼容时说明原因并使用独立环境，正常启动时可自动创建缺失的默认环境。
显式指定的错误路径或不兼容解释器会报错，避免静默更换环境。

```bash
./scripts/setup_teleop_env.sh
./scripts/setup_gello_writer_env.sh v21
./scripts/run_teleop.sh --check-only
./scripts/run_teleop.sh
```

`setup_teleop_env.sh` 只在默认 NRC 环境缺失时调用 `setup_nrc_env.sh`，然后安装
父项目 `.[ui,hdf5,data-validation]`、Dynamixel SDK、RealSense、PyAV 数据校验和 O6 Modbus 依赖。
指定 `GELLO_CR_PYTHON` 或 `NRC_PYTHON` 时须先创建该 Python 3.12 环境。
脚本不安装 `vendor/gello/requirements.txt`，也不向界面进程安装 LeRobot 或训练栈。
正常启动界面且主设备类型为 GELLO 时，会先检查当前解释器的 Dynamixel SDK；缺少时
自动安装并重新检查。安装需要可用的包源和 `uv` 或该解释器的 `pip`，失败时停止启动并提示处理方法。
`--check-only` 只检查配置，不安装或验证该 SDK。

Writer 是独立子进程。默认格式是 `lerobot_v21`，使用官方 `lerobot==0.3.3` 写出 V2.1。
配置仍指向项目默认路径时，优先检查已激活 Conda 中对应格式的 SDK；兼容则直接复用，
不兼容则使用 `module/gello_writers/v21/.venv/bin/python`。Writer 同样要求 Python 3.12。
这与父项目 OpenPI 锁定的 LeRobot 版本不同，不能用 `module/openpi/.venv` 替代。
Writer 安装脚本使用 CPU PyTorch 和 Dataset 依赖，跳过 LeRobot 的训练、可视化和硬件依赖。
运行 SDK API 检查仅证明接口可导入；首次使用新建环境前仍需执行实际写入、合并和恢复测试。

HDF5 使用 NRC 环境中的 `h5py`，相应子进程与界面共享解释器文件，但仍独立运行。
`dataset.worker_pythons` 分别指定 V2.1、V3 和 HDF5；缺少格式项时才回退到
`dataset.worker_python`。`GELLO_CR_DATA_PYTHON` 覆盖启动时所选格式的实际映射；
`GELLO_CR_V21_PYTHON`、`GELLO_CR_V3_PYTHON`、`GELLO_CR_HDF5_PYTHON` 可分别指定解释器，
优先级高于通用变量。覆盖只在内存中生效，不改写配置文件。自定义解释器须通过相应格式检查。
启动日志显示遥操解释器，连接日志显示 GELLO 源码路径，采集准备日志显示 Writer 解释器。

V3 是可选格式，可复用接口兼容的 Conda，否则使用 `module/gello_writers/v3/.venv/`，必须与 V2.1 分离。
其 SDK 需要 `RGBEncoderConfig` 和 `LeRobotDataset.create` 的 streaming encoder 参数。
已有本地验证环境报告为 LeRobot 0.6.2 源码快照，来源没有 Git 元数据；它不能证明某个
PyPI 发布版或固定上游 commit 兼容。因此安装 V3 时必须显式提供已验证的源码或固定 Git spec：

```bash
GELLO_V3_LEROBOT_SPEC=/opt/verified/lerobot \
  ./scripts/setup_gello_writer_env.sh v3
```

NRC、V2.1 与 HDF5 环境由上述脚本安装；V3 安装需显式选择源码。V3 安装结束会检查接口；
仍须针对所选源码完成格式回归后再采集。不要把两个版本装入同一环境，也不要修改 OpenPI 环境解决 Writer 依赖。

## 数据、恢复与日志

最终发布数据写入 `dataset/train/`，采集中及中断批次写入 `dataset/staging/`，
命名轨迹写入 `dataset/replay/trajectories/<uuid>/`。这些目录的生成物均不提交 Git。
训练数据发布前在临时目录校验，成功后原子发布且不覆盖已有目录。
中断恢复先人工处理 Partial，再创建新 Segment；原 Segment、journal 和失败信息保留。
恢复不会自动连接设备、开始采样或恢复运动。详细操作见
[数据格式与恢复说明](teleop/dataset.md)。只读 CLI 校验使用
`./scripts/run_nrc.sh python -m teleop.gello_cr.recording.validate_dataset --help`。

遥操及父工作流日志同时输出到终端和父项目 `logs/teleop.log`，自动保留启动、命令失败及异常堆栈。
操作失败后按界面显示的时间和命令查找日志末尾；无需手动重定向：

```bash
tail -n 150 logs/teleop.log
```

## 诊断与离线工具

从仓库根目录执行 `./scripts/run_nrc.sh python teleop/gello_cr/tools/workbench_diagnostics.py`，
打印解释器、版本、配置和解析后的数据目录，不构造设备会话。
无硬件窗口预览为 `./scripts/run_nrc.sh python teleop/gello_cr/examples/preview_collection.py`。
历史 JSON 的一次性转换使用 `teleop/gello_cr/tools/migrate_legacy_trajectory.py`，见
[迁移说明](teleop/migration_v1.md)；源轨迹保持只读。

## 轨迹预览与人工执行

CLI 支持 UUID 轨迹目录、旧 JSON、LeRobot 数据集或 Parquet，默认只读预览。
预览不构建真实设备连接，先核对轨迹来源、单位、关节选择和回放模式：

```bash
./scripts/run_gello_replay.sh dataset/replay/trajectories/<uuid> --preview
./scripts/run_gello_replay.sh dataset/train/<dataset> --source lerobot --episode-index 0 --preview
./scripts/run_gello_replay.sh --help
```

明确执行需要 `--execute`，该操作会连接选中的设备并使能主臂。以下示例只播放机械臂：

```bash
./scripts/run_gello_replay.sh dataset/replay/trajectories/<uuid> \
  --mode absolute --arm-only --time-scale 0.5 --execute
```

默认模式是 `relative`；绝对/相对模式、选中关节和 Arm/Hand 通道以 `--help` 为准。
TCP delta 动作不作为绝对关节目标回放；PTP 的毫米与共享轨迹的米显式转换。
离线规划结果不能直接执行，必须连接后重新规划。速度、跳变、跟踪和关节 mask 约束仍有效。
父工作台与遥操共享机器人会话锁；已有界面或工作流占用时，另一真实连接会被拒绝。
预览和配置检查不占用机器人会话。

## 父工作流轨迹任务

部署 HMI 可打开 GELLO 采集入口，并添加“共享轨迹（GELLO / LeRobot）”任务。
工作流以已有 NRC/手部会话执行共享 Player；轨迹适配器不创建、使能或关闭第二个会话。
仅播放机械臂时设置 `hand_enabled=false`，需要 O6 时显式开启。

`core/openpi/cr3_o6/run_workflow.py --plan-json` 的任务格式示例：

```json
{
  "tasks": [
    {
      "type": "trajectory",
      "data_dir": "dataset/replay/trajectories/<uuid>",
      "mode": "absolute",
      "hand_enabled": false,
      "repeat": 1,
      "time_scale": 0.5,
      "transition_s": 3.0
    }
  ]
}
```

`data_dir` 相对仓库根目录，UUID 目录是一条轨迹，LeRobot 目录按 Episode 编号读取。
`repeat` 重复整套序列，`time_scale` 大于 1 加速、小于 1 减速。
HMI 保存的任务文件使用 `dataset_dir` / `repeat_count`，由 HMI 转成上述 CLI 字段；不要混用这两种格式。
父工作流没有 CLI 预览开关，应先用上述 GELLO CLI 预览；实际执行时显式确认运动：

```bash
./scripts/run_nrc.sh python core/openpi/cr3_o6/run_workflow.py \
  --config config/hardware/cr3_o6.toml \
  --plan-json '{"tasks":[{"type":"trajectory","data_dir":"dataset/replay/trajectories/<uuid>","mode":"absolute","hand_enabled":false,"repeat":1,"time_scale":0.5}]}' \
  --confirm-motion
```

集成验证仅覆盖离线行为、内存设备和临时数据。真实 CR3/O6/GELLO、三相机采集、
现场运动限制及急停流程尚未联调验收；离线验证通过不表示真机可直接投入使用。
