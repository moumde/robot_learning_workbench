# GELLO 融合后的迁移

正式入口为父项目 `scripts/run_teleop.sh`（`python -m teleop.gello_cr.ui`），配置为
`config/teleop/gello_cr.json` 与 `config/hardware/*.toml`。GELLO 标定、动作库和
HOME/preset 已保留；原工作副本不变。安装与环境、硬件只读字段、采集与恢复见
[集成说明](../gello_cr_integration.md)。

## 源码与工具

遥操的 UI、应用、运动、轨迹、Recorder 和硬件适配都保留在 `teleop/gello_cr/`，
分别放入 `ui/`、`app/`、`motion/`、`trajectory/`、`recording/`、`hardware/` 等职责子目录。
SDK 统一复用父 `vendor/`。
GELLO 设备从 `teleop.gello_cr.devices.gello` 导入，控制策略从
`teleop.gello_cr.control` 下的具体模块导入。独立包、兼容模块和嵌套启动脚本已移除。
UI 生成使用 `module/nrc/.venv/bin/python scripts/generate_collection_ui.py`；数据校验使用
`./scripts/run_nrc.sh python -m teleop.gello_cr.recording.validate_dataset --help`。

诊断和迁移工具位于 `teleop/gello_cr/tools/`，无硬件窗口预览位于
`teleop/gello_cr/examples/preview_collection.py`。维护指南和变更记录统一保存在 `docs/teleop/`。
原嵌套部署配置的本机参考副本保留在忽略目录
`logs/legacy-gello-reference/workbench.json`，不作为运行配置或源码提交。
本机历史计划、审查和验证记录仍作为忽略的本地归档保留。

## 旧轨迹

四份历史 JSON（含 v1 备份）在本机 `dataset/replay/legacy_gello/` 中保留，
不随软件提交。界面可以直接只读导入，也可从仓库根目录转换为共享 UUID Store：

```bash
./scripts/run_gello_replay.sh dataset/replay/legacy_gello/joint_replay.json --preview
./scripts/run_nrc.sh python teleop/gello_cr/tools/migrate_legacy_trajectory.py \
  --root dataset/replay/trajectories dataset/replay/legacy_gello/*.json
```

转换只读源文件，保留关节选择，deg 转 rad，输出 `trajectory.parquet` 与 `meta.json`。
每次转换会生成新 UUID，请按需执行一次。第七轴不作为六轴轨迹通道导入。
生成目录可以在采集窗口中浏览，或作为父工作流 `trajectory` 任务输入。

TCP 数据集回放采用实测关节，不把 TCP delta 当成绝对关节目标。
原 LeRobot 数据仍保持只读；中断批次先处理 Partial，再恢复到新 Segment。
