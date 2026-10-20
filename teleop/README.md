# teleop/

遥操输入设备与具体控制策略。GELLO 设备实现在 `gello_cr/devices/`，映射、运动学和跟随策略位于 `gello_cr/control/`，已有替代主设备适配在 `devices/`。
共享 UI、状态机、Recorder 和设备通信管理属于父 `hmi/collection`、`core/workbench` 与 `core/hardware`。

启动：父项目 `./scripts/run_teleop.sh`。模块导入见 [GELLO 模块](gello_cr/README.md)，迁移边界见 [父级框架](../docs/parent_workbench_framework.md)，维护指南位于 [docs/teleop](../docs/teleop/architecture.md)。
