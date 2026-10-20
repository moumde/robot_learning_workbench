# 父级采集与遥操框架

共享实现已归入 robot_learning_workbench 父目录，GELLO 模块负责主设备及控制策略。

- `hmi/collection/`：Qt 窗口、页面、Controller、Designer `.ui`、生成绑定、QSS。
- `core/workbench/app/`、`core/workbench/core/`：应用状态、命令、权限、运行时、HOME 与采集编排。
- `core/workbench/motion/`、`trajectory/`、`recording/`：运动仲裁、轨迹/规划、采集、writer、恢复和合并。
- `core/workbench/bootstrap/`、`composition.py`：父级组合入口与硬件配置。
- `core/hardware/`：机器人适配、O6 单线程通信、相机管理与原生 RGB 采样后端。
- `teleop/gello_cr/devices/`、`control/`：GELLO 反馈、映射、校准、运动学和跟随策略。

## 运行

从父项目执行 `./scripts/setup_teleop_env.sh`；安装对象是父目录 `pyproject.toml`，复用 NRC/UI 环境，writer 继续使用独立环境。

```bash
./scripts/run_teleop.sh
./scripts/run_teleop.sh --check-only
./scripts/run_gello_replay.sh --help
module/nrc/.venv/bin/python scripts/generate_collection_ui.py
```

正式 Python 入口为 `python -m hmi.collection`，回放入口为 `python -m core.workbench.replay`。代码直接使用父命名空间和 `teleop.gello_cr.control.*`、`teleop.gello_cr.devices.gello`；独立兼容包与嵌套启动脚本已移除，安装由父 `pyproject.toml` 管理。

诊断工具为 `./scripts/run_nrc.sh python tools/workbench_diagnostics.py`，只读数据校验为
`./scripts/run_nrc.sh python -m core.workbench.recording.validate_dataset --help`。
[无硬件窗口预览](../examples/README.md)、[详细架构](teleop/architecture.md)、
[配置](teleop/configuration.md)、[数据集](teleop/dataset.md)、[硬件](teleop/hardware.md)和
[迁移](teleop/migration_v1.md)均从父目录维护。

## 设备所有权

CR3A 适配持有一个父 `vendor.nrc_interface.interface.CR3Interface`，所有连接、读取和目标发送经过该实例。NRC 会话适配只转换旧 degree×7 接口与父 rad×6+外部轴接口，并保留 MoveJ 调度和 busy 处理。父对象独占端点锁，关闭不完整时继续保留资源用于重试。

相机组只持有一个父 `CR3O6CameraInterface`，串号视图共用这一个实例。采集 UI 采用可注入的原生 RGB 后端，保留独立物理采样时间和单一采集线程；父部署默认 LeRobot 读帧行为保持。UI 只读采样服务的缓存状态，不等待设备连接锁。读取缓存不会生成新采样时间。

O6 worker 已归入 `core/hardware/o6.py`，在单一线程中复用父 vendor 的 O6 驱动，保留目标去重、故障恢复、取消和 hold。

## 配置与数据

硬件仍由 `config/hardware/*.toml` 提供。GELLO 标定、任务与运行参数由 `config/teleop/gello_cr.json` 提供，硬件字段不可在采集设置中覆盖。数据分别写入 `dataset/train/`、`dataset/staging/`、`dataset/replay/`；没有改写已有数据契约、训练或 Policy 推理代码。

## 离线验证

```bash
module/nrc/.venv/bin/python -m pytest -q
module/nrc/.venv/bin/python tools/simulate_collection.py --duration 300 \
  --output logs/parent-simulation-new-run \
  --v21-python module/gello_writers/v21/.venv/bin/python \
  --v3-python /absolute/path/to/v3/bin/python \
  --hdf5-python module/nrc/.venv/bin/python
```

仿真工具走父 `WorkbenchRuntimeFactory`、父 Robot/Camera、真实 Qt 状态更新与 writer。仅替换硬件信号并写隔离测试目录，不连接真实设备。报告记录 FPS、相机帧复用/采样延迟、GUI 心跳、异常与退出线程；相机硬件丢帧数未统计时保持 unknown。
