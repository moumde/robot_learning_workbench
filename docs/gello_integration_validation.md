# GELLO 融合验证记录

2026-10-17；父基线 `86f249a`，导入来源 `euiiue/gello_CR@f9e442c`。
分支 `codex/gello-cr-integration-20261017`；远端新克隆位于
`/home/ubuntu/cyf/robot_learning_workbench-integrated-20261017`，原工作区保持不变。

## 实施结果

遥操模块位于 `teleop/gello_cr`，复用根 vendor 的 NRC、O6 与 GELLO SDK。
父硬件 TOML 提供连接、七轴 ServoJ、左右手地址及三相机参数；设置页只读显示。
采集、恢复与轨迹分别使用 `dataset/train`、`dataset/staging`、`dataset/replay/trajectories`。
父工作流借用已有 NRC/手部会话执行共享 Player，真实连接由同一端点锁互斥。

移除了嵌套 SDK 与失效的嵌套 CI；旧入口和诊断/迁移工具统一转交父配置。
四份历史轨迹 JSON（含备份）移入本地 `dataset/replay/legacy_gello`，保留原文件，
只读转换为四条 UUID Store 轨迹；软件提交减少约 12.8 万行现场数据。

## 验证结果

- 完整离线套件：957 通过，包含官方 V2.1/V3 与 HDF5 实际写入、跨格式数据一致性和中断恢复。
- Designer 再生成后的实际 Qt 界面、入口和交互回归：73 通过。
- 新安装正式环境：38 项实际三格式写盘/恢复及父集成验证通过；初次缺 PyAV 的三项失败补齐正式依赖后全部重跑通过，其余 35 项通过。
- 定向 Ruff、五个启动/安装脚本语法与暂存 diff 检查通过。
- 新环境启动和真实 Qt 离屏渲染成功：OFFLINE、相机停止、未自动连接硬件。
- 历史数据转换、诊断工具执行成功，未改写输入数据。

只读集成审查发现并修复：无 observation.state 的旧 PTP 数据丢失 TCP 目标；
左手 profile 未映射 0x28 地址。两处均有失败复现和修复后的回归。
实际部署还修复了父 OpenPI 客户端 NumPy 1.x 与新版 OpenCV/PyArrow 的冲突，
以及发布/恢复校验缺少 PyAV 的依赖问题。

## 已安装环境

NRC/GELLO 使用 Python 3.12.15、NumPy 1.26.4、OpenCV 4.11.0.86、
PyArrow 21.0.0、Qt Essentials 6.12.0、h5py 3.16.0、PyAV 15.1.0。
V2.1 独立环境使用 LeRobot 0.3.3、CPU Torch 2.7.1、torchvision 0.22.1、
NumPy 2.5.2、PyArrow 26.0.0、datasets 3.6.0 与 PyAV 15.1.0。
新环境导入共享 NRC SDK、父 HMI 和 OpenPI client 成功；未改训练环境。

V3 验证使用已有 `/tmp/gello-v3-test-env`，对应 LeRobot 0.6.2 本地源码快照，
没有可追溯的 Git commit；未将它冒充固定发布版，也没有改写成 V2.1 环境。
新机器启用 V3 时须显式提供兼容源码并运行格式验证。

未连接或移动真实 CR3/O6/GELLO，未打开真实相机；现场运动、断线、物理急停和长时采集仍需现场联调。
