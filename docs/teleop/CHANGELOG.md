# Changelog

## 未发布 — 父工作台源码整理（2026-10-20）

- 移除独立包兼容入口和嵌套脚本，正式入口统一为父 `hmi.collection`、共享回放 CLI 与父启动脚本。
- GELLO 设备和控制策略分别归入 `teleop/gello_cr/devices/`、`control/`；共享实现保留在父 `core/` 与 `hmi/`。
- 工具、离线示例和维护指南统一放在父 `tools/`、`examples/`、`docs/teleop/`。重复配置保留为忽略的本地参考副本，运行配置使用 `config/teleop/gello_cr.json` 和硬件 TOML。

## 未发布 — Designer 与采集工作流（2026-10-17）

- 八份 Qt Designer 表单替代主要手写静态布局，QSS 外置并打包；采集 Controller、相机预览和跨页状态分别维护。
- 增加真实机器人描述与能力接口，持续显示身份、Servo、输入、Teleop、REC、Dataset、Episode、FPS 和来源错误。
- 统一按钮与命令许可；HOME 要求明确使能且停止运动，录制锁定设备和格式切换，Finish 明确结果后一次停止并保存，Discard 确认一次。
- Servo 反馈使用受管缓存；主动下使能/断开与异常失联分离，快照不等待设备 I/O 或磁盘持久化。
- 修复正式运行时 readiness 未读取机器人缓存的问题：在组合入口显式注入状态快照，连接、Servo、反馈过期与错误同步进入界面和共享许可。
- 相机失联/过期清空失效预览、停止采样并保留 Pending；区分采样槽跳过、迟帧、重复和未知丢帧，保存后展示回执。
- 恢复批次自动采用原格式，失败还原选择；保留 profile 校验、新 Segment 和人工 Partial 决策。
- 完整离线回归 903 项通过，无跳过；独立审查问题已修复并复核。真实设备验收仍待现场执行。

## 1.0.0 — 发布准备（2026-10-16，现场验收待签收）

- 统一 CR3A + O6 + GELLO 工作台：正式 HMI 入口、六页界面、统一命令策略，启动保持 OFFLINE。
- Teleop、HOME、轨迹回放、Joint / TCP / Waypoint 规划共享 MotionCoordinator 和 lease；回放及规划轨迹使用同一 Player。STOP / FAULT / ESTOP 抢占后不自动恢复运动。
- 轨迹使用 UUID / Parquet Store；兼容只读导入旧 JSON 和 LeRobot Episode，增加一次性迁移工具。
- 采集抽象为 CaptureFrame / Session / Writer，支持独立环境中的 LeRobot V2.1、V3 和 HDF5；增加批次、Segment、journal、Partial 决策、恢复与校验后原子发布。
- 初始独立版本集中维护配置；现已迁入父 `config/teleop/gello_cr.json` 与 `config/hardware/*.toml`，集中校验、原子保存和部署路径解析；保留现场标定、HOME、O6 动作与历史输入。
- 拆分应用服务，明确后台任务、反馈线程与 Worker 的归属、关闭顺序和失败重试；增加统一日志、领域错误和无硬件诊断。
- 清理根目录旧入口、兼容桥接与重复 UI 策略；保留已配置的 RoArm / Inverse3 和 GELLO 控制模式；新增开发/部署文档与离线 CI。

现场设备要求见 [硬件说明](hardware.md)。版本号不代表真机验收通过。

### 2026-10-17 整体结构审查

- 将现有 P0–P9 工作区作为统一基线审查，验证应用服务、命令通道、运动与录制的边界及退出重试。
- 保留 GELLO 物理采样时间戳与反馈失效处理，以及统一界面主题和对话框中的软件急停快捷键。
- 当前完整官方格式离线回归 834 项通过，无跳过；生产代码 lint、格式、编译和 diff 检查通过。真机部署仍需按硬件说明完成现场核对。
