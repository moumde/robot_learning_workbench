# Legacy Audit

本表记录 P9 对迁移残留的处置。依据为当前生产 import、正式入口、配置选择与离线回归；不是按文件名或创建年代判定废弃。P0–P8 功能、现场标定、HOME、原始录制和旧轨迹输入均保留。DELETE 指删除重复代码或旧入口，不能据此删除用户数据。

| 原项 / 类别 | 决定 | 当前去向与理由 |
| --- | --- | --- |
| 根 `teleop_runtime.py` | MOVE | Runtime Facade、ConfigStore、控制映射和设备适配归入 `src/gello_cr/app`、`control`、`devices`，生产 import 不再经根模块 |
| 根 `lerobot_recorder.py` | MOVE | 通用采样、Schema、Worker 与格式后端归入 `recording/`；三种 Writer 共用 Session |
| `src/gello_cr/app/workflow_ui.py`、旧 UI 预览实现 | DELETE / MOVE | 移除重复 UI 许可策略；正式策略来自 ApplicationService，合成预览移到 `examples/preview_ui.py` |
| 旧 recording 的 `episode_recorder.py`、`worker_service.py`、bootstrap `sample_source.py` | MOVE | 由 `recording/session.py`、`source.py`、`worker_loop.py` 及格式 Worker 承担；不再保留并行生产实现 |
| `TEST_INEXBOT.py`、`run_test_inexbot.sh` | DELETE | 旧原型硬件入口不再提供第二套启动和运动路径 |
| `TELEOP_README.md` | DELETE | 由根 README 和 `docs/` 替代，避免操作流程分叉 |
| 根 `test_teleop_runtime.py`、`test_gello_collection.py` | MOVE | 功能回归归入 `tests/`；共用 Fake Devices 放在 `tests/fakes/` |
| `tests/v2/test_legacy_*_bridge.py` 等旧桥接测试 | DELETE | 随已移除兼容桥接一起删除；现行 Runtime、设备、Recording 和 HMI 功能回归继续保留 |
| `config/roarm_cr5_teleop.json` | MOVE | `config/workbench.json` 为唯一正式配置；历史标定、动作和 pose 内容保留 |
| `config/joint_replay*.json` 四个旧输入 | MOVE | `examples/legacy_trajectories/`；只读适配，不能当部署配置加载 |
| `scripts/run_operator.sh` | WRAPPER / KEEP | 唯一正式 HMI shell 入口，定位解释器和仓库后调用 `gello_cr.ui` |
| `scripts/replay_trajectory.py`、安装命令 `gello-replay` | WRAPPER | 调用 `gello_cr.cli.replay_trajectory` 和统一 Player；不是第二套 Runtime |
| `scripts/validate_dataset.sh` | WRAPPER / KEEP | 调用只读格式校验入口，数据解释器可单独指定 |
| `devices/roarm.py`、`inverse3.py` | KEEP | RuntimeFactory 仍按 `master.type` 选择，属于可配置替代主臂，不是未引用残留 |
| GELLO 的 joint / XYZ / TCP 模式、FK 几何映射 | KEEP | ConfigStore 和 TeleopController 仍使用，需分别现场验收 |
| `devices/nrc_robot.py`、`vendor/nrc` | KEEP | NRC 会话适配及原生 SDK；需与 Python ABI 匹配 |
| `vendor/gello`、`vendor/linker_hand_python_sdk` | KEEP | 当前 GELLO / O6 适配器依赖；LinkerHand 为上游子模块 |
| `vendor/robotiq_sensor` 的旧 Python 包装 | DELETE | 当前 CR3A + O6 运行路径没有使用；不声称提供 Robotiq 力传感支持 |
| A/B/C/D 旧快捷运动及重复 enablement | DELETE / KEEP DATA | 统一精确走点替代旧操作，移除 `recall_preset` 及自动恢复跟随分支；HOME 独立保留。配置中的旧 pose 数据保留，不自动执行 |
| DAgger/OpenPI 集成 | KEEP | 显式可选外部集成，经应用命令与统一运动仲裁，核心 HMI 不要求训练环境 |
| 原始 Dataset、journal、Segment 和 legacy JSON | KEEP | 迁移与发布生成新输出；不自动改写源文件或删除采集证据 |

`app/runtime.py` 保留 Facade；跟随、HOME、手动作、轨迹和采集快照已拆为内聚服务。运行中的反馈、完成通知和相机发现任务必须有明确 owner 和关闭路径，详见 [架构说明](architecture.md)。
