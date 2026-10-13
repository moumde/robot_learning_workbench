# Robot Learning Workbench

Robot Learning Workbench 是一个面向机器人学习研发的基线工程。它把 OpenPI 算法框架、硬件适配、训练/部署脚本和协同开发约定放在同一个仓库中，目标是让新成员能够：

- 用一条明确的流程完成环境部署；
- 在固定版本的 OpenPI 上复现实验；
- 在不污染算法环境的前提下接入 NRC 机器人和其他硬件；
- 使用统一的脚本启动训练、服务端、客户端和硬件测试。

当前基线面向 Ubuntu 22.04、`uv` 和常见 NVIDIA GPU 开发场景。CPU 机器可以完成部分导入和接口测试，但训练和 GPU 推理仍需要匹配的 NVIDIA 驱动、CUDA/JAX/PyTorch 环境。

## 1. 环境边界

本项目明确维护两套 Python 环境：

| 用途 | 环境目录 | Python | 启动方式 |
| --- | --- | --- | --- |
| OpenPI 训练、模型服务端、相机/LeRobot 相关程序 | `module/openpi/.venv/` | 由 OpenPI 的 `.python-version` 固定，当前为 3.11 | `./scripts/run_openpi.sh ...` |
| NRC 机器人客户端、NRC 厂商动态库和网络部署程序 | `module/nrc/.venv/` | 3.12 | `./scripts/run_nrc.sh ...` |

NRC 厂商动态库 `_nrc_host.so` 按 Python 3.12 构建，因此不要在 OpenPI 的 Python 3.11 进程中直接导入它。模型服务端和机器人客户端通过网络协议通信，两个进程可以运行在同一台机器或不同机器上。

这两个环境都不应安装到工作台根目录 `.venv`，也不要使用系统 Python 执行 `pip install`。

### 1.1 硬件配置入口

硬件连接信息统一放在 `config/hardware.toml`，包括：

- NRC 的 IP、控制/示教/跟踪端口、连接超时和 ServoJ 参数；
- LinkerHand 的左右手、型号、关节数量、状态范围、RS485/CAN 传输方式和设备路径；
- D435 的逻辑名称、序列号、采集尺寸、输出尺寸、FPS 和读取超时。

NRC 配置中的几个连接参数含义如下：

| 参数 | 作用 |
| --- | --- |
| `connect_control` | 是否额外连接 `6000` 控制端口；为 `false` 时只连接示教端口 `6001` 和跟踪端口 `7000`。当前接口主要使用 `6001` 读取状态/执行状态操作、使用 `7000` 执行 ServoJ，`6000` 作为可选连接保留。 |
| `connection_timeout` | 单个端口从发起连接到连接状态就绪的最长等待时间，单位为秒。 |
| `connection_poll_period` | 连接建立后检查连接状态的轮询间隔，单位为秒。默认 `0.2` 表示每 200 ms 检查一次。 |

推荐保持以下配置，除非现场控制器的网络响应特性有变化：

```toml
[nrc]
connect_control = false
connection_timeout = 10.0
connection_poll_period = 0.2

[nrc.ports]
control = 6000
teach = 6001
track = 7000
```

`config/hardware.py` 是配置中间层。它负责读取和校验 TOML，并提供接口工厂：

```python
from config.hardware import load_hardware_config

hardware = load_hardware_config()
robot = hardware.create_nrc_interface()
cameras = hardware.create_d435_interface()
hand_kwargs = hardware.hand.api_kwargs()
```

其他程序应优先复用这套配置和工厂，不要再次在业务代码中复制 IP、端口、相机序列号或图像规格。现场机器需要不同配置时，可以通过 `--config /path/to/hardware.toml` 指定另一份 TOML；不要把包含账号、密钥的配置提交到仓库。

## 2. 快速开始

### 2.1 获取代码

维护者创建团队仓库后，其他开发者直接克隆项目：

```bash
git clone <团队仓库 SSH 或 HTTPS 地址> robot_learning_workbench
cd robot_learning_workbench
```

### 2.2 安装系统工具和 uv

Ubuntu/Debian 用户可以执行：

```bash
./scripts/install_system_deps_ubuntu.sh
```

脚本会安装 Git、Git LFS、编译工具、OpenGL/FFmpeg 等常用依赖，不会安装或修改 NVIDIA 驱动。

如果系统还没有 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

### 2.3 创建并验证 OpenPI 环境

```bash
./scripts/bootstrap.sh
```

该脚本会根据项目内 OpenPI 的 `pyproject.toml` 和 `uv.lock` 创建 `module/openpi/.venv/`，然后检查以下模块是否可以导入：

- `openpi`
- `lerobot`
- `jax`
- `torch`
- `cv2`

也可以分开执行：

```bash
./scripts/setup_openpi_env.sh
./scripts/verify_openpi_env.sh
```

验证主机 GPU：

```bash
nvidia-smi
```

没有 GPU 时，环境 smoke test 仍可能通过，但不能据此认为训练或 GPU 推理可用。

### 2.4 创建 NRC Python 3.12 环境

只有需要 NRC 机器人、NRC 部署客户端或 NRC 接口测试时才需要执行：

```bash
./scripts/setup_nrc_env.sh
```

该脚本创建 `module/nrc/.venv/`，安装 OpenPI 的轻量客户端包以及 NRC/LinkerHand 网络和 RS485 测试需要的基础依赖。启动 NRC 程序时使用：

```bash
./scripts/run_nrc.sh python <程序路径> [参数]
```

例如：

```bash
./scripts/run_nrc.sh python test/test_nrc_interface.py
```

`run_nrc.sh` 会检查 Python 3.12，并为 NRC 厂商动态库补充对应的 Python 共享库路径。

## 3. 常用开发流程

### 3.1 运行 OpenPI 程序

```bash
./scripts/run_openpi.sh python -c \
  "import sys, openpi, lerobot, jax, torch; print(sys.executable); print(jax.devices())"
```

`run_openpi.sh` 会自动：

- 使用 `module/openpi/.venv/`；
- 将当前工作目录切换到 `module/openpi/`；
- 通过 OpenPI 项目配置运行命令。

因此，从仓库根目录运行工作台测试文件时，需要使用相对于 `module/openpi/` 的路径，例如：

```bash
./scripts/run_openpi.sh python ../../test/test_hand_camera.py
```

### 3.2 训练

训练配置和参数以项目内 `module/openpi/` 的 OpenPI 源码为准：

```bash
./scripts/run_openpi.sh scripts/train.py \
  <config_name> --exp-name=<experiment_name>
```

不要直接复制其他 OpenPI 版本的配置名称。实际可用配置请查看：

```text
module/openpi/src/openpi/training/config.py
```

当前基线已经迁移了 Dobot CR3 + LinkerHand O6 的 Pi05 LoRA 配置：

```bash
./scripts/run_openpi.sh scripts/train.py \
  pi05_cr3_o6_lora --exp-name=pi05_cr3_o6_lora
```

该配置使用 `module/openpi/src/openpi/policies/cr3_o6_policy.py` 完成三路图像、12 维状态/动作与 Pi05 32 维动作头之间的适配：输入数据使用 12 维动作，模型内部补齐到 32 维，推理输出再裁剪回 12 维。训练前需要准备 LeRobot 数据集 `local/data_v21`，并让它位于 `HF_LEROBOT_HOME/local/data_v21`；也可以将配置中的 `repo_id` 改为团队实际使用的 Hugging Face 数据集 ID。数据字段应包含：

- `observation.images.base_0_rgb`
- `observation.images.left_wrist_0_rgb`
- `observation.images.right_wrist_0_rgb`
- `observation.state`（12 维）
- `action`（12 维）

其中基座相机必须存在；策略变换层对缺失的腕部相机会使用黑图和无效 mask，但数据集的 repack 字段仍应与上述命名保持一致。首次准备数据时，可先计算归一化统计量：

```bash
./scripts/run_openpi.sh scripts/compute_norm_stats.py pi05_cr3_o6_lora
```

默认统计文件会写入 `module/openpi/assets/pi05_cr3_o6_lora/local/data_v21/`。如果团队使用其他数据集 ID，应同步修改配置中的 `repo_id`，并重新计算统计量。

### 3.3 启动模型服务端

模型服务端应使用 OpenPI 环境。当前基线不强行规定唯一的服务端入口，接入具体服务程序后按实际文件运行：

```bash
./scripts/run_openpi.sh python <server_program>.py [参数]
```

服务端脚本和参数以当前项目实现为准。启动后，部署客户端通过网络访问服务端，不需要在客户端环境中安装完整训练栈。

### 3.4 启动部署客户端

部署客户端使用 NRC 3.12 环境：

```bash
./scripts/run_nrc.sh python deploy/<client_program>.py [参数]
```

如果客户端还需要 D435 相机、LinkerHand 或其他厂商 SDK，应将这些依赖安装到客户端实际使用的环境，并在团队文档或依赖清单中记录，不能只依赖个人机器上的临时安装。

## 4. 硬件测试

### 4.1 NRC 机械臂接口测试

默认是只读测试，会从 `config/hardware.toml` 读取 IP 和端口，连接示教端口 `6001` 和跟踪端口 `7000`，读取伺服状态、关节位置、TCP 位姿，并检查笛卡尔位姿转关节接口：

```bash
./scripts/run_nrc.sh python test/test_nrc_interface.py
```

临时覆盖机器人 IP：

```bash
./scripts/run_nrc.sh python test/test_nrc_interface.py --ip 192.168.2.14
```

可选参数：

```bash
# 跳过笛卡尔转关节检查
./scripts/run_nrc.sh python test/test_nrc_interface.py \
  --ip 192.168.2.14 --skip-cartesian

# 同时连接控制端口 6000
./scripts/run_nrc.sh python test/test_nrc_interface.py \
  --ip 192.168.2.14 --connect-control

# 受监督地测试 ServoJ 控制路径
./scripts/run_nrc.sh python test/test_nrc_interface.py \
  --ip 192.168.2.14 --control-test
```

`--connect-control` 会覆盖配置中的 `connect_control`，使测试额外连接 `6000`；`--no-connect-control` 可以强制关闭该连接。`connection_poll_period` 只影响连接建立阶段的状态检查频率，不会改变 ServoJ 控制周期。

`--control-test` 可能会执行上电、打开 ServoJ、发送当前关节位置和下电操作。即使目标位置是当前值，也必须确认机器人周围安全并由人员现场监护。

### 4.2 LinkerHand 与 D435 测试

测试默认通过 OpenPI 环境运行，因为相机接口复用了 OpenPI/LeRobot 的 RealSense 实现：

```bash
./scripts/run_openpi.sh python ../../test/test_hand_camera.py
```

默认从 `config/hardware.toml` 读取手的传输方式、设备路径和相机参数。临时使用 CAN 或覆盖 RS485 设备时：

```bash
./scripts/run_openpi.sh python ../../test/test_hand_camera.py \
  --transport can --can can0
```

该测试只连接右手 O6、读取当前手指状态、连接三台 D435 并读取图像，不发送手部运动命令。

运行前需要确认：

- LinkerHand SDK 位于 `vendor/actuator/linkerhand-python-sdk/`；
- RS485 时串口设备存在且当前用户有权限访问；
- CAN 时 `can0` 已正确配置；
- 三台 D435 的序列号与 `config/hardware.toml` 中的配置一致；
- OpenPI 环境中已经具备 LeRobot RealSense 后端、`pyrealsense2` 以及 LinkerHand SDK 所需的硬件依赖。

RS485 测试至少需要 `pymodbus==3.5.1` 和 `pyserial`。如果 OpenPI 环境还没有这些包，应安装到 OpenPI 环境，而不是系统 Python：

```bash
uv pip install --python module/openpi/.venv/bin/python \
  pymodbus==3.5.1 pyserial
```

LinkerHand SDK 的完整依赖清单位于：

```text
vendor/actuator/linkerhand-python-sdk/requirements.txt
```

安装完整清单前请先评估它与 OpenPI 锁定依赖的兼容性；硬件专用依赖应由团队统一记录。

## 5. 仓库结构

```text
robot_learning_workbench/
├── vendor/                 # NRC、相机、末端执行器等硬件适配
├── config/                 # 运行时硬件配置和配置中间层
├── teleop/                 # 遥操功能
├── hmi/                    # 数据采集、训练和部署界面
├── module/
│   ├── openpi/             # OpenPI 源码，由本项目直接管理
│   │   └── src/openpi/policies/
│   │                       # OpenPI 策略与机器人动作/观测适配
│   └── nrc/                # NRC 独立环境目录，不提交 .venv
├── core/                   # 工作台核心业务逻辑
├── tasks/                  # 训练任务、业务流程和部署任务定义
├── test/                   # 接口、相机和硬件测试
├── dataset/
│   ├── train/              # 训练数据，不进 Git
│   └── replay/             # 回放轨迹，不进 Git
├── checkpoints/            # 模型权重，不进 Git
├── thirdparty/             # 确实需要 vendoring 的第三方代码
├── scripts/                # 部署、环境、验证和启动脚本
└── logs/                   # 本地运行日志，不进 Git
```

OpenPI 源码只维护在 `module/openpi/`，不要复制到工作台其他目录。工作台自己的业务代码应放在 `core/`、`vendor/`、`teleop/`、`hmi/` 等目录中。

## 6. 脚本说明

| 脚本 | 用途 |
| --- | --- |
| `scripts/install_system_deps_ubuntu.sh` | 安装 Ubuntu/Debian 系统工具和基础库 |
| `scripts/bootstrap.sh` | 创建并验证 OpenPI 环境 |
| `scripts/setup_openpi_env.sh` | 按 OpenPI 锁文件安装 `module/openpi/.venv/` |
| `scripts/verify_openpi_env.sh` | 检查 OpenPI、LeRobot、JAX、Torch、OpenCV 和 GPU |
| `scripts/run_openpi.sh` | 在 OpenPI 3.11 环境和 OpenPI 工作目录中运行命令 |
| `scripts/setup_nrc_env.sh` | 创建独立的 Python 3.12 NRC 客户端环境 |
| `scripts/run_nrc.sh` | 在 NRC 环境、仓库根目录中运行命令 |

日常运行 Python 程序时，优先使用对应的启动脚本，不要直接调用系统 `python`。这可以避免 Python 版本、当前工作目录和动态库搜索路径不一致。

## 7. 协同开发规则

### 7.1 OpenPI 代码由本项目管理

OpenPI 源码已经完整放在 `module/openpi/` 下，并作为本项目普通文件提交。其他成员只需同步工作台仓库：

```bash
git init -b main
git add .
git commit -m "chore: add robot learning workbench baseline"
git remote add origin <团队仓库 SSH 或 HTTPS 地址>
git push -u origin main
```

```bash
git pull --ff-only
```

`module/openpi/` 下的 CR3/O6 配置和策略修改属于本项目代码，不会自动提交或推送到 OpenPI 上游项目。更新 OpenPI 版本时，由维护者在本项目中统一替换和验证。

### 7.2 依赖变更需要可复现

- OpenPI 依赖以 `module/openpi/pyproject.toml` 和 `module/openpi/uv.lock` 为准。
- 不要单独拉取或复制另一套 LeRobot；当前 OpenPI 版本会声明和锁定它需要的 LeRobot。
- 不要在系统 Python 上安装项目依赖。
- 工作台新增依赖时，要说明属于 OpenPI 环境、NRC 环境还是系统/ROS 环境。
- 需要长期保留的依赖必须进入脚本、依赖清单或正式文档，不能只在个人环境中手动安装。
- ROS 2 Humble、相机驱动和厂商 SDK 可以有独立的系统依赖，不要未经评估直接塞进 OpenPI 锁定环境。

### 7.3 不提交生成物

以下内容默认不进入 Git：

- `.venv/`、Python 缓存和构建产物；
- 数据集、回放轨迹、模型 checkpoint；
- 运行日志、临时文件和个人配置；
- 任何包含设备 IP、账号或密钥的本地配置。

提交前检查：

```bash
git status --short
git diff --check
```

## 8. 日常更新

同步团队代码：

```bash
git pull --ff-only
```

通常不需要每次重新安装环境。只有以下情况才运行相应脚本：

- OpenPI 的 `pyproject.toml` 或 `uv.lock` 发生变化：运行 `./scripts/setup_openpi_env.sh`；
- NRC 客户端依赖或 Python 版本发生变化：运行 `./scripts/setup_nrc_env.sh`；
- `module/openpi/` 源码发生变化：同步后按需重新运行 `./scripts/setup_openpi_env.sh` 和 `./scripts/verify_openpi_env.sh`。

更新 OpenPI 前，维护者应先在独立分支中完成环境、导入和关键流程验证。

## 9. 常见问题

### `module/openpi` 源码缺失

请确认项目克隆完整，并检查 `module/openpi/pyproject.toml` 是否存在。

### `run_openpi.sh` 找不到环境

执行：

```bash
./scripts/setup_openpi_env.sh
./scripts/verify_openpi_env.sh
```

### NRC 报 Python 版本或 `libpython3.12.so` 错误

不要使用 `run_openpi.sh` 启动 NRC 程序。执行：

```bash
./scripts/setup_nrc_env.sh
./scripts/run_nrc.sh python test/test_nrc_interface.py \
  --ip 192.168.2.14
```

### RS485 报 `No module named pymodbus`

确认依赖安装在实际运行测试的环境中。`test_hand_camera.py` 使用 OpenPI 环境，因此安装命令应指向：

```bash
uv pip install --python module/openpi/.venv/bin/python \
  pymodbus==3.5.1 pyserial
```

NRC 客户端则使用 `setup_nrc_env.sh` 创建的 `module/nrc/.venv/`。

### 相机无法连接

优先检查：

- `pyrealsense2` 是否安装在 OpenPI 环境；
- 相机 USB 连接、权限和序列号；
- `camera_interface.py` 中的序列号是否与实际设备一致；
- 是否已经安装并启用了 RealSense 所需的系统组件。

### GPU 未发现

`verify_openpi_env.sh` 会区分“Python 包可导入”和“GPU 可用”。先检查：

```bash
nvidia-smi
```

然后确认 NVIDIA 驱动、CUDA 运行库和当前 OpenPI 锁定的 JAX/PyTorch 组合兼容。

## 10. 官方参考

- [OpenPI 官方仓库](https://github.com/Physical-Intelligence/openpi)
- [OpenPI 安装说明](https://github.com/Physical-Intelligence/openpi#installation)
- [Astral uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)
- [uv 项目同步与锁文件](https://docs.astral.sh/uv/concepts/projects/sync/)
