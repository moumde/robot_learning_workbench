# 遥操模块与父项目边界

遥操的实际实现集中在 `teleop/gello_cr/`，Python 文件按职责分入子目录。
父项目提供共用 SDK、运行环境、配置、数据目录、日志目录和启动脚本。
操作者请先看 [遥操快速开始](../teleop/README.md)。

## 源码位置

- `teleop/gello_cr/ui/`：Qt 窗口、页面、Controller、Designer `.ui`、生成绑定和 QSS。
- `teleop/gello_cr/app/`、`core/`：应用命令、状态机、权限、运行时及采集编排。
- `teleop/gello_cr/motion/`、`trajectory/`、`recording/`：运动仲裁、轨迹与规划、采集、Writer、恢复和合并。
- `teleop/gello_cr/bootstrap/`：配置组合、硬件注册和应用创建。
- `teleop/gello_cr/hardware/`、`devices/`、`control/`：机器人、O6、相机和主设备适配，GELLO 映射、标定及跟随策略。
- `teleop/gello_cr/cli/`、`support/`：命令行入口、路径、日志、诊断和数据契约。
- `teleop/gello_cr/tools/`、`examples/`、`tests/`：离线工具、预览和模块测试；父 `test/` 保留跨模块集成测试。

父 `hmi/` 保留部署界面。

## 运行与维护

从父项目执行 `./scripts/setup_teleop_env.sh`；安装对象是父目录 `pyproject.toml`，
复用 NRC/UI 环境，Writer 继续使用独立环境。

```bash
./scripts/run_teleop.sh
./scripts/run_teleop.sh --check-only
./scripts/run_gello_replay.sh --help
module/nrc/.venv/bin/python scripts/generate_collection_ui.py
```

正式 Python 入口为 `python -m teleop.gello_cr.ui`，回放入口为
`python -m teleop.gello_cr.cli.replay`。独立兼容包与嵌套启动脚本已移除。
诊断工具为 `./scripts/run_nrc.sh python teleop/gello_cr/tools/workbench_diagnostics.py`，只读数据校验为
`./scripts/run_nrc.sh python -m teleop.gello_cr.recording.validate_dataset --help`。
[无硬件窗口预览](../teleop/gello_cr/examples/README.md)、[详细架构](teleop/architecture.md)、
[配置](teleop/configuration.md)、[数据集](teleop/dataset.md)、[硬件](teleop/hardware.md)和
[迁移](teleop/migration_v1.md)提供进一步说明。

## SDK 与设备所有权

SDK 只在父 `vendor/` 维护，不在遥操目录复制。CR3A 适配持有一个
`vendor.nrc_interface.interface.CR3Interface`，所有连接、读取和目标发送经过该实例。
NRC 会话适配转换 degree×7 与父 rad×6+外部轴接口，并保留 MoveJ 调度和 busy 处理。
父 SDK 对象独占端点锁，关闭不完整时保留资源用于重试。

相机组只持有一个父 `CR3O6CameraInterface`，串号视图共用该实例。采集 UI 使用
可注入的原生 RGB 后端，保留独立物理采样时间和单一采集线程。
UI 只读采样缓存，不等待设备连接锁；读取缓存不会生成新采样时间。

`teleop/gello_cr/hardware/o6.py` 在单一线程中复用父 vendor 的 O6 驱动，
保留目标去重、故障恢复、取消和 hold。

## 配置、数据与日志

硬件由 `config/hardware/*.toml` 提供；GELLO 标定、任务与运行参数由
`config/teleop/gello_cr.json` 提供，硬件字段不可在采集设置中覆盖。
数据写入父 `dataset/train/`、`dataset/staging/`、`dataset/replay/`。
遥操及父工作流的运行和失败上下文自动写入父 `logs/teleop.log`。

## 离线验证

```bash
module/nrc/.venv/bin/python -m pytest -q teleop/gello_cr/tests test
module/nrc/.venv/bin/python teleop/gello_cr/tools/simulate_collection.py --duration 300 \
  --output logs/teleop-simulation-new-run \
  --v21-python module/gello_writers/v21/.venv/bin/python \
  --v3-python /absolute/path/to/v3/bin/python \
  --hdf5-python module/nrc/.venv/bin/python
```

仿真工具走 `WorkbenchRuntimeFactory`、Robot/Camera 适配、真实 Qt 状态更新与 Writer。
仅替换硬件信号并写隔离目录，不连接真实设备。报告记录 FPS、相机帧复用/采样延迟、
GUI 心跳、异常与退出线程；相机硬件丢帧数未统计时保持 unknown。
