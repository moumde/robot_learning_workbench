# 历史轨迹数据

导入源中的四份历史 JSON（包括 v1 备份）保留在父项目
`dataset/replay/legacy_gello/`。这些现场数据不再随软件代码提交；原始项目中的文件保留不变。

从父仓库根目录运行只读预览：

```bash
./scripts/run_gello_replay.sh dataset/replay/legacy_gello/joint_replay.json --preview
```

轨迹转换与正式存储见父项目 `docs/gello_cr_integration.md`。
