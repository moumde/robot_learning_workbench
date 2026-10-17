# GELLO 融合后的迁移

正式入口为父项目 `scripts/run_teleop.sh`，配置为 `config/teleop/gello_cr.json` 与
`config/hardware/*.toml`。GELLO 标定、动作库和 HOME/preset 已保留；原工作副本不变。
安装与环境、硬件只读字段、采集与恢复见 [集成说明](../../../docs/gello_cr_integration.md)。

## 旧轨迹

四份历史 JSON（含 v1 备份）在本机父目录 `dataset/replay/legacy_gello/` 中保留，
不随软件提交。界面可以直接只读导入，也可从父仓库根目录转换为共享 UUID Store：

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

## 原入口

`teleop/gello_cr/scripts/run_operator.sh`、`scripts/replay_trajectory.py` 和已安装的
`gello-replay` 命令均使用父工作台配置与连接所有权。诊断与迁移工具同样默认读取父配置，
不再使用本目录的 `config/workbench.json` 标定参考。
