# GELLO 遥操模块

此目录只维护 GELLO 主设备、关节/手部映射、运动学、标定和跟随策略。
设备实现在 `devices/gello.py`，控制策略在 `control/`，由父工作台组合运行。

```python
from teleop.gello_cr.devices.gello import GelloDevice, GelloFeedback
from teleop.gello_cr.control.controller import TeleopController
```

从仓库根目录安装和启动：

```bash
./scripts/setup_teleop_env.sh
./scripts/run_teleop.sh --check-only
./scripts/run_teleop.sh
./scripts/run_gello_replay.sh --help
```

采集界面位于 `hmi/collection/`，共享运行时、轨迹和 Recorder 位于 `core/workbench/`，
机器人、O6 和相机适配位于 `core/hardware/`。应用复用 `module/nrc/.venv/`；
LeRobot Writer 使用父项目独立环境。运行配置由 `config/teleop/gello_cr.json` 和
`config/hardware/*.toml` 提供，启动保持 OFFLINE / IDLE。

安装、配置和设备边界见 [集成说明](../../docs/gello_cr_integration.md)及
[父级框架](../../docs/parent_workbench_framework.md)。详细指南位于
[docs/teleop](../../docs/teleop/architecture.md)，版本记录见
[CHANGELOG](../../docs/teleop/CHANGELOG.md)。诊断、轨迹转换和离线窗口预览分别位于
`tools/workbench_diagnostics.py`、`tools/migrate_legacy_trajectory.py` 和
`examples/preview_collection.py`。
