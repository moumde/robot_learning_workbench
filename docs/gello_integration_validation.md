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

## 2026-10-18：HOME 停止与掉线恢复修复

HOME 停止/退出改为等待单次操作完成，而非常驻命令线程；真实卡住时仍超时并保留设备。
掉线链路恢复后，人工复位重新挂接原会话；持续断线时，处理 Episode 后允许从 FAULT
显式断开并重新连接，重连保持未使能，不恢复运动。断开前仍确认旧运动生产者已退出。

原 GELLO 分支完整离线回归 912 通过；同步至融合工作区后，生产环境相关回归 106 通过。
本轮没有连接真实设备。


## 2026-10-19：共享框架归入父项目并复用父 Robot / Camera

Qt 实现、Designer 文件与 QSS 迁至 `hmi/collection`；状态机、遥操运行时、运动/轨迹、
Recorder、writer 与恢复归入 `core/workbench`。机器人、O6 和相机通信归入 `core/hardware`。
GELLO 设备与控制映射留在 `teleop/gello_cr`；旧 `gello_cr.*` 是同一实现的兼容导入。

CR3A 实际持有父 `CR3Interface`，共享唯一 SDK 通道和端点锁；相机共用父
`CR3O6CameraInterface`，保留真实采样时间。修复了首次反馈失败/部分断开仍显示连接的问题，
以及慢相机连接持锁阻塞 UI 快照的问题。HOME、故障锁存和恢复不自动跟随的规则保留。

安装入口归父级 `pyproject.toml`；已在 NRC/UI 环境完成父级 editable 安装，
从 `/tmp` 执行新旧入口检查均为 OFFLINE，无自动硬件连接。八份 Designer 绑定已再生成。

- 最终完整离线回归：**991 通过，86.85 秒**；三格式实际写盘、读回与中断恢复包含在内。
- 定向 Ruff、启动脚本语法、`git diff --check` 通过；只读收尾审查未发现新的明确问题。
- 父级组合入口持续仿真：正常录制 **300.004 秒**，三个 Episode 各 2,001 帧，共 **6,003 帧**，约 **19.995 FPS**。
- Qt 20 ms 心跳的 p95 间隔为 21.547 ms，最大 48.432 ms；无未处理异常、无残留应用 worker。
- 覆盖丢弃、GELLO/相机/机器人/O6 异常、软件急停、显式复位、重连与退出；恢复不会自动跟随。
- 最终三格式读回：V2.1 六个 Episode/6,126 帧；HDF5 一个/61 帧；V3 一个/61 帧。
- 父轨迹桥接成功读入 2,001 帧，O6 反馈变化和开合目标均已落盘读回。

报告与截图位于 `logs/parent-framework-stability-20261019/`，详见 `report.json`。
这是通过父 RuntimeFactory、父 Robot/Camera、真实 Qt 与 writer 的仿真，硬件信号被替换，
数据写入隔离目录；未验证真实 SDK 通信、实体运动与物理急停。相机硬件丢帧数仍为 unknown，
帧复用、采样延迟与需要复核的质量标志按实际记录保留。V3 仍使用前述本地源码快照。

框架与启动说明见 [parent_workbench_framework.md](parent_workbench_framework.md)。本轮未提交或推送。
