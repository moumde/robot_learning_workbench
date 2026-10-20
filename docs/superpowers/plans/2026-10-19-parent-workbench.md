# Parent Workbench Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or executing-plans to implement task-by-task.

**Goal:** 把共享采集/遥操框架与设备通信归入父项目，并实际使用父 Robot/Camera 类。

**Architecture:** core/workbench 持有业务与状态，core/hardware 组合父设备类，hmi/collection 持有 Qt 页面；GELLO 策略留在 teleop。旧导入只作兼容，所有实例/枚举共用一份实现。

**Tech Stack:** Python 3.12、PySide6、Qt Designer、既有 NRC/O6/RealSense 与独立数据 writer。

**Spec:** docs/superpowers/specs/2026-10-19-parent-workbench-design.md

## Global Constraints

保留现有未提交修复；不改安全阈值、数据契约、训练与 policy 推理。保持 OFFLINE 启动、显式使能、故障锁存、恢复不自动运动、单一硬件所有者。.ui/QSS 与独立 writer 环境保持。

## Review Focus

- 兼容导入不得生成两份枚举或破坏 monkeypatch/private helper。
- 机器人不能双重持锁或保留第二组 SDK fd；rad/deg 与第七轴不能丢失。
- 缓存相机帧不得在读取时刷新采样时间；断线需使采集失效。
- 父 UI/worker 资源定位不能依赖原嵌套目录或运行 cwd。
- HOME/停止/断线恢复与未处理 Episode 的规则不退化。

## Tasks

- [x] 1. 迁移公共业务模块至 core/workbench，GELLO 控制策略与输入设备保留 teleop；补同一类型的旧导入兼容。验证状态/生命周期/停止/录制回归。
- [x] 2. 在 core/hardware 统一 CR3A/NRC/O6，实际组合父 CR3Interface；新增最小可注入 API 与必要父类能力。验证父目标发送、单位、连接/使能/停止/故障及锁所有权。
- [x] 3. 在 core/hardware 建父三相机组及单采样后端，快照保留真实采样时间。验证父相机调用、掉线/过期/关闭与 raw/处理帧语义。
- [x] 4. 将 Qt UI 实现/.ui/QSS 迁到 hmi/collection，改父入口、生成器、安装/资源定位、轨迹桥接；保留旧命令兼容。验证实际离屏窗口、原部署入口兼容。
- [x] 5. 更新引用实现路径的必要测试和文档，运行父级完整离线回归、writer 实际写盘与父入口持续仿真。审查后修复实证问题，记录结果。

## Execution

在现有隔离融合分支 codex/gello-cr-integration-20261017 中连续实施。用户已明确要求实施；不重复请求设计/执行批准。共享目录及 canonical 导入映射由 /tmp/workbench-parent-package-map.json 固定，互不覆盖。
