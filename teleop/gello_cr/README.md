# GELLO 遥操模块

日常安装和采集操作见 [遥操快速开始](../README.md)。所有命令从父项目根目录运行，
安装由父 `pyproject.toml` 管理，应用使用 NRC Python 环境，LeRobot Writer 使用独立环境。

遥操实现按职责放在本目录的子文件夹中：

- `ui/`：采集窗口、页面、Presenter、Designer 表单和样式。
- `app/`、`core/`：应用服务、命令、状态机、配置和权限。
- `bootstrap/`：配置组合、设备注册和应用创建。
- `devices/`、`hardware/`：GELLO 等主设备、CR3A、O6 和相机适配；SDK 复用父 `vendor/`。
- `control/`、`motion/`：GELLO 标定与映射、跟随策略、运动仲裁和执行。
- `trajectory/`、`recording/`：轨迹、规划、采集、Writer、恢复和数据发布。
- `cli/`、`support/`：命令行入口、路径、日志、诊断和数据契约。
- `tools/`、`examples/`、`tests/`：离线工具、窗口预览和模块测试。

正式入口为 `python -m teleop.gello_cr.ui`，回放入口为
`python -m teleop.gello_cr.cli.replay`，日常通过父启动脚本使用：

```bash
./scripts/run_teleop.sh
./scripts/run_gello_replay.sh --help
```

配置、数据和日志仍共用父项目的 `config/`、`dataset/`、`logs/`。
详细边界见 [父项目与模块](../../docs/parent_workbench_framework.md)，
配置及环境见 [集成说明](../../docs/gello_cr_integration.md)，
离线工具见 [示例](examples/README.md)，历史变更见 [CHANGELOG](../../docs/teleop/CHANGELOG.md)。
