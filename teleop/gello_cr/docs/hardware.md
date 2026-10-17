# 硬件与 SDK 部署

正式 Profile 是 `cr3a_o6`，面向 CR3A + O6，默认主臂为 GELLO。硬件支持代码存在不代表该部署已完成现场验收；v1.0 的签收状态见 [发布清单](release_v1.md)。

## 适配边界

| 设备 | 代码与依赖 | 打开时机 |
| --- | --- | --- |
| CR3A / NRC | `devices/cr3a.py` 生命周期、`nrc_robot.py` 会话；`vendor/nrc` 的 Python wrapper 与匹配原生扩展 | 明确“连接机器人”；连接后不使能 |
| GELLO | `devices/gello.py`；`vendor/gello`、`dynamixel-sdk`；FK 模式使用配置 URDF | 明确准备设备 |
| O6 | `devices/o6.py`；`vendor/linker_hand_python_sdk/LinkerHand`，上游子模块及 `pymodbus==3.5.1` | 明确准备设备；RS485 SDK 由唯一 `O6-RS485` 线程拥有 |
| RealSense RGB | `devices/realsense.py`、`pyrealsense2` | 明确启动相机；每个唯一序列号一个物理流 |
| RoArm（可选主臂） | `devices/roarm.py`，串口通信 | `master.type=roarm` 并明确准备 |
| Inverse3（可选主臂） | `devices/inverse3.py`，外部 Inverse Service、`websocket-client`（`alternative-masters` extra） | `master.type=inverse3` 并明确准备 |

应用以 Linux x86-64 / Python 3.12 为仓库 NRC 原生扩展部署基线；不要混用其他 Python ABI 的 `_nrc_host`。保持 SDK wrapper 与扩展成对，默认位于 `vendor/nrc`；可用 `robot.sdk_root` 或更高优先级 `NRC_SDK_ROOT` 覆盖。`run_operator.sh` 为选中解释器添加库路径。GELLO 和 LinkerHand 的代码位置由仓库及配置定位；克隆后初始化子模块：

```bash
git submodule update --init --recursive
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui,dev]'
```

GELLO SDK 需要提供 `DynamixelRobot.get_joint_state_sample()`，返回标定后的关节值和最后一次成功总线读数的 `time.monotonic()` 时间戳；重复读取缓存不得刷新该时间戳。仓库 `vendor/gello` 已实现该接口，当前 `gello.software_root=../vendor/gello` 使用它。若改用外部 GELLO SDK，必须提供同样的物理采样接口；缺少接口时应用在创建设备前拒绝连接，不以轮询时间代替硬件反馈新鲜度。总线持续失败超过 `gello.feedback_timeout_s` 或读取线程报错会使反馈失效，需要排故后由操作者重新连接。

实际连接环境另安装匹配设备 SDK。LeRobot / HDF5 属于独立 Worker 环境，参见 [Dataset](dataset.md)，不要为了界面启动把多个 LeRobot 大版本混装。

## 上电前核对

核对控制器 IP/端口与机器人编号、GELLO/O6 的 by-id 串口及权限、设备 ID、相机序列号和物理画面。保留并逐项确认 `joint_offsets`、`joint_signs`、夹爪端点、O6 动作和 HOME，尤其检查从其他现场复制配置后是否仍适用。可选 GELLO `xyz_j6`、`xyz_j6_tcp_ik`、`tcp_6d` 使用不同映射/运动学路径，需要分别验收。

仓库没有可代替现场安全评估的机械限位或工作空间数值。`motion.joint_limits_rad`、`workspace_limits_m` 需要由设备/工装实际约束提供；软件速度、跳变、跟踪阈值也必须现场确认。NRC ServoJ 参数和 O6 原始速度/力矩参数的设备含义不得与 SI 单位混淆。

## 显式操作与断连

启动 OFFLINE → 连接机器人 → 准备主臂和手 → 上使能 → 开始遥操作；相机按需要单独启动。上使能不会自动跟随，切页不会打开设备，复位不会续播或续录。复位只可能恢复应用此前明确要求的使能状态，不能把原本未使能的连接静默上使能。

STOP、软件急停、主臂丢失、机器人断连、相机过期、O6 故障都需要观察实际设备反馈。F12 不代替物理急停。软件不自动重连继续运动；排故后由操作者明确复位和重新启动动作。O6 单电机恢复只允许实现支持的故障类别，恢复前覆盖旧目标，不能对温度、编码器或供电故障反复强制恢复。

只读软件身份诊断：

```bash
.venv/bin/python tools/diagnostics.py
```

该命令不加载 SDK、不连接设备，`connected_devices={}` 不能作为连接或运动验收证据。现场需记录控制器/固件、SDK 版本、物理急停结果和性能实测值；用 [发布清单](release_v1.md) 逐项签收。
