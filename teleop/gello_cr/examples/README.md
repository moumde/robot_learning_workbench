# 离线示例

从仓库根目录使用 NRC/UI 环境预览采集窗口：

```bash
./scripts/run_nrc.sh python teleop/gello_cr/examples/preview_collection.py
```

该示例只创建应用服务、Presenter 和窗口，不构造机器人、主臂、O6 或相机；命令只写日志。
正式采集使用 `./scripts/run_teleop.sh`。需要完整采集与 Writer 仿真时使用
`teleop/gello_cr/tools/simulate_collection.py`，参数见其 `--help`。

本机历史 JSON（包括 v1 备份）保留在 `dataset/replay/legacy_gello/`，不随软件提交。
只读预览与一次性转换见 [迁移说明](../../../docs/teleop/migration_v1.md)。
