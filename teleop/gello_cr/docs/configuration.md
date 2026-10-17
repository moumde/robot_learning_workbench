# 配置、单位与环境覆盖

唯一正式部署配置为 `config/workbench.json`。`TeleopConfigStore.from_file()` 要求文件存在，缺失会明确报错，不会静默启动默认硬件配置。加载时合并 `DEFAULT_CONFIG` 补充缺省字段；显式保存的 O6 动作库作为完整库，不自动补回已删除动作。设置保存先校验，再写同目录 `.tmp` 并 `os.replace`。在连接设备前修改，保存后重启应用。

## 部署身份与连接

| 配置组 / 字段 | 含义与单位 |
| --- | --- |
| `version` | 配置版本，当前为 1；与软件版本 `1.0.0` 不同 |
| `hardware.profile` / `name` | 目前只接受 `cr3a_o6`；name 为显示名称 |
| `master.type` | `gello`、`roarm` 或 `inverse3`，仅构造选中的主臂 |
| `robot.ip`、`command_port`、`servo_port`、`robot_num` | 控制器地址、整数端口 1..65535、机器人编号 1..4 |
| `robot.sdk_root` | 可选 NRC SDK 目录，包含匹配的 `nrc_interface.py` 与原生扩展 |
| `gello.port` / `roarm.port` / `o6.port`、`baudrate` | 串口及波特率；部署优先使用 `/dev/serial/by-id/` |
| `inverse3.uri`、设备 ID、`basis` | Inverse Service 的 ws/wss 地址、设备标识、坐标基定义 |
| `feedback_hz` / `feedback_timeout_s` | 对应主臂反馈频率 Hz、过期阈值秒；频率须有限且为正 |
| `logging.level`、`ui.refresh_ms` | 日志级别；GUI 刷新毫秒，整数且至少 20 |

正式机器人生命周期使用 ServoJ；`robot.motion_mode` 和 MoveJ 参数仍为底层适配和历史模式保留，不能据此认为 HMI 会切换成独立 MoveJ 遥操实现。

## 标定、运动与规划

| 配置组 / 字段 | 单位与解释 |
| --- | --- |
| `gello.joint_ids` / `joint_offsets` / `joint_signs` | 六关节 ID、rad 标定偏置、±1 方向；`locked_joints` 为 1..6 的不重复编号 |
| `gello.joint_scale` | 无量纲关节倍率 0.5..1.5；`gripper_config` 为夹爪 ID 与原始端点 |
| `gello.control_mode` | `joint`、`xyz_j6`、`xyz_j6_tcp_ik`、`tcp_6d`；非 joint 模式需有效 URDF |
| `gello.xyz_axis_map`、`xyz_scale`、`j6_sign` | 3×3 坐标映射、XYZ 倍率、J6 方向；`software_root` / `kinematics_urdf` 为路径 |
| `teleop.scale_xyz` / `scale_rpy` | 无量纲跟随倍率 |
| `teleop.max_delta_xyz_mm` / `max_delta_rpy_rad` | 相对起点的 XYZ 范围 mm / 姿态范围 rad |
| `teleop.max_tcp_speed_mm_s` / `max_tcp_angular_speed_rad_s` | TCP 线速度 mm/s / 角速度 rad/s |
| `teleop.max_master_jump_mm` / `max_master_angular_jump_rad` | 主臂单帧跳变 mm / rad；`period_s` 为控制周期秒 |
| `robot.safety_max_command_step_rad`、`safety_max_command_speed_rad_s` | GELLO 关节跳变 rad、速度 rad/s；`safety_speed_violation_cycles` 为连续帧数 |
| `robot.safety_max_tracking_error_rad` | 目标与反馈的跟踪误差 rad |
| `robot.servoj_vmax` / `amax` / `jmax`、`movej_velocity` / `acc` / `dec` | 原样传入 NRC 接口的控制参数；须按现场 SDK/控制器定义核定，不能当作 SI 速度限值 |
| `robot.movej_period_s`、`movej_max_segment_deg`、`movej_duplicate_deadband_deg` | 秒、单段角度 deg、去重死区 deg |
| `preset.robot_*_percent`、`timeout_s` | HOME 的速度/加减速百分比、等待上限秒 |
| `presets.HOME` | 保留现场示教：`robot_joints_deg` 为 deg，`robot_tcp` 前三维 mm、RPY rad，GELLO/RoArm 关节 rad，O6 原始值 |
| `replay.sample_period_s` / `servoj_period_s` / `mode_switch_settle_s` | 轨迹录制周期 / 回放周期 / 模式稳定时间，均为秒 |
| `replay.max_duration_s` / `max_joint_speed_deg_s` | 录制时长秒、回放速度上限 deg/s |
| `planning.max_joint_velocity_rad_s` / `max_joint_acceleration_rad_s2` | 规划关节速度 rad/s、加速度 rad/s²；标量或六维 |
| `planning.max_linear_velocity_m_s` / `max_angular_velocity_rad_s` | 规划 TCP 速度 m/s、rad/s；`default_speed_scale` 为 (0,1] 倍率 |
| `planning.joint_sample_hz`、`tcp_position_step_m`、`tcp_rotation_step_deg`、`max_ik_step_rad` | Hz、m、deg、rad |
| `planning.reached.*` | 反馈到位容差：关节 deg、位置 mm、姿态 deg；稳定样本数、超时秒、采样周期秒 |

`motion.joint_limits_rad` 可配置六个 `[min,max]`，`motion.workspace_limits_m` 可配置 XYZ 三个 `[min,max]`。可选 `motion.max_command_delta_rad` 与 `max_target_velocity_rad_s` 用于目标保护。仓库不提供经现场认可的绝对关节或工作空间数值；未配置就是没有该项软件绝对边界，不能解释成无限安全范围。现有部署文件保留历史标定和阈值，数值通过软件校验不等于现场安全签收。

## 数据、手和快捷键

`o6.open` / `closed` / `actions` / `speed` / `torque` 均是六维 0..255 设备原始值；`command_deadband` 也是原始值，反馈与动作超时单位为秒。`open_action` / `closed_action` 必须引用动作库已有项。不要把设备原始 speed/torque 值解释为 rad/s 或 Nm。

`dataset` 指定 `format`、`recording_mode`、`root`、可选 `staging_root`、`worker_python` / `worker_pythons`、`fps`、`image_size`、相机配置和质量阈值。`image_size=[height,width]`，偶数像素；`camera_max_age_s` / `camera_max_skew_s` / `action_max_age_s` 为秒，`max_tracking_error_deg` 为 deg，ROI 为 0..1 归一化坐标。详见 [Dataset](dataset.md)。

`trajectory.root` 是 UUID 轨迹库目录。`shortcuts` 只绑定正式命令，空字符串表示不绑定，非空快捷键不能重复。保留的旧 A/B/C/D pose 数据不会生成旧快捷运动命令；新的走点经统一规划、预览和执行。

## 路径与环境变量

`resolve_path()` 先展开 `~`，再把相对路径放在配置文件目录下并解析；因此 `../dataset/replay/trajectories` 指向仓库 `dataset/replay/trajectories`。部署转换处理数据 root/staging、Worker Python、轨迹目录、GELLO 软件/URDF 和配置中的 NRC SDK 路径。绝对路径保持绝对；不会通过环境变量修改配置文件。

| 环境变量 | 用途和优先级 |
| --- | --- |
| `GELLO_CR_PYTHON` | `run_operator.sh` 的应用解释器；未设置先用项目 `.venv/bin/python`，再回退 `python3.12` |
| `GELLO_CR_DATA_PYTHON` | 覆盖数据 Worker 的回退解释器，也用于 `validate_dataset.sh`；格式专属 `worker_pythons[format]` 优先 |
| `NRC_SDK_ROOT` | NRC SDK 环境覆盖优先于 `robot.sdk_root` 和仓库 `vendor/nrc`；建议绝对路径；更换 SDK 后重启防止混载 |
| `GELLO_CR_OPENPI_ROOT` | 可选 DAgger 外部 OpenPI 根目录；只有显式启动集成时使用 |
| `GELLO_CR_REPO_ROOT` | 直接 `python -m gello_cr.ui` 的默认仓库定位；正式脚本显式传入自身仓库目录 |
| `GELLO_TEST_V21_PYTHON` / `GELLO_TEST_V3_PYTHON` | 仅官方格式离线回归的 Worker 环境，不是运行时配置 |

启动脚本设置本仓库 `src` 的 `PYTHONPATH` 和解释器库路径。`tools/diagnostics.py` 打印版本、Git commit、解释器、Profile 和解析后的数据路径，不构造设备会话。缺少文件、非法 Profile、端口、采样频率或规划约束应先修正配置，不通过绕过校验来启动。
