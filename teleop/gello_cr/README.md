> 共享框架已迁入父项目，完整边界见 [父级框架说明](../../docs/parent_workbench_framework.md)。

# Robot Learning Workbench v1.0

此目录已集成到父工作台。当前安装、共享硬件配置、数据路径和启动方式以
[父项目集成说明](../../docs/gello_cr_integration.md)为准；从仓库根目录执行
`./scripts/setup_teleop_env.sh`、`./scripts/run_teleop.sh`。
下文保留独立版本的功能说明，`config/workbench.json` 是原始标定参考，
运行配置使用父目录 `config/teleop/gello_cr.json` 与 `config/hardware/*.toml`。
此目录的 `scripts/run_operator.sh` 和 `scripts/replay_trajectory.py` 会转交父项目入口。

面向 **CR3A + O6 + GELLO** 的统一机器人学习工作台：遥操作、运动仲裁、轨迹录制与回放、
Joint / TCP / Waypoint 规划，以及 LeRobot V2.1、V3、HDF5 数据采集和中断恢复。

正式 HMI 入口只有 **`scripts/run_operator.sh`**。启动为 OFFLINE / IDLE，不自动连接、使能、
跟随或恢复运动。真实设备部署与现场核对见 [硬件说明](docs/hardware.md)。

## 安装与配置

从父仓库根目录执行 `./scripts/setup_teleop_env.sh`。界面和设备复用 NRC Python 3.12
环境；LeRobot V2.1、V3 Writer 使用独立环境，不修改 OpenPI 的训练依赖。
具体环境安装命令见 [集成说明](../../docs/gello_cr_integration.md)。

连接端点、ServoJ 七轴参数、O6 串口和三台相机来自 `config/hardware/*.toml`；
标定、映射、安全阈值、动作库和采集设置来自 `config/teleop/gello_cr.json`。
设置页显示所选硬件 profile 的只读参数，保存其他设置不改写硬件 TOML。
本目录 `config/workbench.json` 保留导入时的标定参考，不是运行配置。

路径相对配置文件目录解析，环境覆盖不写回配置。首次连接前核对 GELLO 标定、
关节方向、HOME 和现场运动限制。关节与 TCP 绝对限位尚未提供；
现有跳变、速度和跟踪阈值继续生效。

## 启动与遥操作

```bash
scripts/run_operator.sh
```

兼容入口转交父项目 `scripts/run_teleop.sh`，默认使用父 NRC 环境；
可用 `GELLO_CR_PYTHON=/path/to/python3.12` 指定应用环境。
依次人工执行 **选择配置 → 连接机器人 → 确认状态 → Servo On → 连接 GELLO / O6 → 开始遥操作**。
使能本身不启动跟随。需要采集图像时再启动相机。

六个页面是数据采集、轨迹与回放、精确走点、数据集管理、机器人状态、设置。
顶部持续显示当前机器人、Robot、Servo、输入设备、Teleop、Recording、Dataset、Episode 和采集 FPS。
设备反馈未知时明确显示未知，错误横幅跨页面保留；页面切换不连接设备或发起运动。
停止运动、软件紧急停止和 HOME 始终位于主窗口，HOME 仅在明确使能、运动停止且无待处理 Episode 时可用。

采集页按连接、Servo On、连接遥操设备、启用遥操四个步骤显示状态和下一步提示。
相机区支持拖动分隔线调整空间，主画面与两路辅助画面分别显示 FPS 和时龄。
右侧优先显示当前 Episode、计时、帧数、FPS、开始 / 完成并保存 / 丢弃操作；
数据集会话建立后自动收起任务与保存设置，可手动展开查看。
未完成批次通过底部入口查看，不会打断当前页面。

STOP 撤销当前运动权，结束后保持停止。F12 是软件紧急停止，不能代替控制柜物理急停。
FAULT / ESTOP 需排故后人工复位，复位不恢复跟随、回放或录制。
退出时明确处理未保存 Episode 和轨迹；确认后停止采样和运动，再关闭相机、主臂、手、机器人和 Worker。
失败会保留错误并允许重试，不能静默保存成功或丢弃数据。

## 数据采集

采集页填写简短任务名称和训练任务描述，选择父目录、格式，创建数据集。
遥操运行且相机就绪后，每条 Episode 按 **开始录制 → 执行操作 → 选择成功 / 失败结果 → 完成本段并保存** 操作。
完成并保存由同一后台命令停止采样和保存，成功后显示 Episode、结果、帧数与保存位置。
丢弃只确认一次；普通录制不反复弹窗。故障、断流或全局停止留下 Pending 时，明确保存失败或丢弃；
零帧不能保存成有效 Episode。故障复位前必须先处理本段数据。
任务名称用于目录，描述保存在训练 task 中；创建批次后格式和任务锁定。
处理上一条 Episode 后才能开始下一条。最后“结束数据集”完成合并、校验和发布。

三路逻辑图像可以来自三台相机，也可以沿用两台相机 + Base ROI：

- `observation.images.base_0_rgb`：Base RGB。
- `observation.images.left_wrist_0_rgb`：Wrist RGB。
- `observation.images.right_wrist_0_rgb`：默认 Base ROI，键名兼容历史数据。

录制周期和 GUI 刷新分离。每路显示 FPS、Age、OK / STALE / OFFLINE。
joint 模式记录实际关节与已接受的绝对关节目标（rad）及 O6；tcp 模式记录关节 + TCP 状态和
TCP delta 动作（m/rad）。详细维度和时间戳含义见 [Dataset](docs/dataset.md)。
回放或走点期间可以独立采集 Episode，需明确选择对应采集来源；不能在 HOME 或空闲状态启动普通采集。
运动结束不替用户保存 Episode。录制期间锁定设备切换、数据格式、任务、HOME 和普通断开操作。
相机失联或画面过期会清空失效预览并停止采样，保留待处理数据；跳过采样槽、迟帧和相机重复分别统计，
没有相机序列丢失计数时“丢帧”明确显示未统计。

## 轨迹与规划

“轨迹与回放”支持命名录制、停止保存、取消、预览，以及相对 / 绝对回放。
轨迹保存在 `TrajectoryStore` 的 UUID 目录，包含 Parquet 和元数据，不依赖 Dataset Writer。
回放可选关节、Arm / Hand、倍率和重复次数；所有运动经过同一 MotionCoordinator。
旧 JSON 和 LeRobot Episode 可导入轨迹，源数据只读。

“精确走点”支持 Joint PTP、TCP PTP、TCP Linear 和 Waypoint，先规划预览，再明确执行。
规划器生成 Trajectory，通过同一 Player 执行，并检查真实反馈到位。
离线 Joint 预览需要明确输入起点，保存的离线计划不能直接执行；连接后需重新规划。
TCP 规划需要实际运动学服务；当前 NRC IK 只有单解，不能保证找到全部分支。

`scripts/replay_trajectory.py` / `gello-replay` 是调用同一 Player 的 CLI；只读预览和人工明确执行
见其 `--help`。它们不是第二套运行时。A/B/C/D 旧同步示教点回位由统一规划功能取代。

## 中断恢复与校验

“数据集管理”分别展示已发布和可恢复批次。启动扫描只读，不自动恢复设备或采样。
选择批次后检查 Partial，明确标为 Failure 或丢弃，再恢复到新 Segment。
恢复自动采用原批次格式，仍要求机器人与采样配置一致；恢复不会自动连接设备、运动或开始采样。
最终合并重新生成连续索引，在临时目录校验成功后原子发布；原 Segment 和 journal 保留。
丢弃批次是逻辑标记，不删除原文件；已有训练数据不会自动改写。

列表的 UNCHECKED 仅表示本次未显式校验。点击校验使用对应格式 Worker，显示 VALID / INVALID。
也可用 `scripts/validate_dataset.sh --help` 查看只读校验参数。

## 架构与目录

从 [架构说明](docs/architecture.md) 了解依赖边界、权威状态和线程归属。

```text
父 hmi/collection/        Qt UI、Designer 表单和 QSS
父 core/workbench/        应用、状态机、运动、轨迹与 Recorder
父 core/hardware/         父 Robot/Camera 组合与 O6 通信管理
父 config/                统一硬件和遥操配置
父 dataset/               数据集、恢复批次和回放
teleop/gello_cr/           GELLO 设备、映射和跟随策略
src/gello_cr/              过渡兼容导入；无重复实现
```

版本变化见 [CHANGELOG](CHANGELOG.md)。
可选 DAgger 集成仍使用外部 OpenPI 项目，设置 `GELLO_CR_OPENPI_ROOT` 后在高级区域显式启动；
模型接口须在部署环境联调，核心工作台不依赖 OpenPI。

## 开发验证

主要静态布局维护在 父 `hmi/collection/forms/`，使用 Qt Designer 编辑；Python 负责信号、状态和动态字段。
修改 `.ui` 后运行 父 `module/nrc/.venv/bin/python scripts/generate_collection_ui.py`，提交表单和 `hmi/collection/generated/` 生成结果，不手工编辑生成代码。
统一样式位于 父 `hmi/collection/styles/app.qss`。机器人身份与能力由 `RobotDescriptor` / `RobotCapabilities` 提供，
目前只注册真实支持的 `cr3a_o6` 配置；增加驱动时沿用同一采集页，不复制整页。

```bash
# 在父 robot_learning_workbench 根目录运行
./scripts/setup_teleop_env.sh
module/nrc/.venv/bin/python -m pytest -q
module/nrc/.venv/bin/python scripts/generate_collection_ui.py
git diff --check
```

默认测试禁止真实 SDK 和设备打开；真实设备测试必须显式标记 `hardware` 并单独选择
`pytest -m hardware`。现场部署和设备核对见 [硬件说明](docs/hardware.md)，CI 不驱动硬件。
完整官方格式回归需另设 `GELLO_TEST_V21_PYTHON` 和 `GELLO_TEST_V3_PYTHON`。
未提供时这些测试会说明原因并跳过，其他离线功能照常运行。
CI 只运行离线检查；没有文件哈希比对或额外冒烟测试框架。

## 排障

- 连接前先核对串口权限、by-id 和设备固件；软件不自动重连或继续运动。
- Worker 启动失败：核对 `worker_python` 是否存在及该环境的官方格式 SDK，查看 stderr 错误。
- 相机 STALE：检查对应物理序列号及流 Age / Skew；ROI 复用同一物理流。
- 运动被拒绝：查看 Owner、速度 / 跳变 / 跟踪阈值及当前状态，不通过提高阈值掩盖原因。
- 获取版本、Git commit、Python、Profile 和数据配置：`python tools/diagnostics.py`。
  机器人状态页另提供显式反馈读取；日志采用 UTC 时间，默认 INFO，不逐帧打印。
