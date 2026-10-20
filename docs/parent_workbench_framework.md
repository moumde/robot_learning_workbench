# 父级采集与遥操框架

共享实现已归入 robot_learning_workbench 父目录，GELLO 模块负责主设备及控制策略。

- `hmi/collection/`：Qt 窗口、页面、Controller、Designer `.ui`、生成绑定、QSS。
- `core/workbench/app/`、`core/workbench/core/`：应用状态、命令、权限、运行时、HOME 与采集编排。
- `core/workbench/motion/`、`trajectory/`、`recording/`：运动仲裁、轨迹/规划、采集、writer、恢复和合并。
- `core/workbench/bootstrap/`、`composition.py`：父级组合入口与硬件配置。
- `core/hardware/`：机器人适配、O6 单线程通信、相机管理与原生 RGB 采样后端。
- `teleop/gello_cr/`：GELLO 反馈、映射、校准和跟随策略；旧 `gello_cr` 导入暂保留兼容层。

## 运行

从父项目执行 `./scripts/setup_teleop_env.sh`；安装对象是父目录 `pyproject.toml`，复用 NRC/UI 环境，writer 继续使用独立环境。

```bash
./scripts/run_teleop.sh
./scripts/run_teleop.sh --check-only
./scripts/run_gello_replay.sh --help
module/nrc/.venv/bin/python scripts/generate_collection_ui.py
```

正式 Python 入口为 `python -m hmi.collection`。旧 `python -m teleop.gello_cr` 与 `gello_cr.ui` 命令转到同一父实现；没有第二份窗口、状态机或 Recorder。嵌套打包配置已迁到父级。

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


2026-10-19 验证：完整离线回归 991 通过；父级组合持续录制 300 秒、6,003 帧、约 19.995 FPS，
并完成设备故障恢复、三格式保存读回和退出清理。详细证据与范围见
[gello_integration_validation.md](gello_integration_validation.md#2026-10-19共享框架归入父项目并复用父-robot--camera)。
