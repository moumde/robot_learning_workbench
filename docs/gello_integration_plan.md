# GELLO 集成实施计划

日期：2026-10-17。目标基准：`moumde/robot_learning_workbench@86f249a`。导入源：`euiiue/gello_CR@f9e442c`。

## 目标与边界

将经过离线验证的 GELLO 遥操、数据采集、轨迹与规划实现放入 `teleop/gello_cr/`，复用根目录 SDK、硬件 profile、数据目录和既有任务流。保留两项目现有运动停止、故障和数据恢复语义，不修改模型训练或 Policy 推理实现，不连接或移动真实设备。

用户已明确要求拉取、融合适配和稳定性测试；以下设计和实现属于该授权范围。保留原工作区，在远端的新克隆中建立 `codex/gello-cr-integration-20261017`。

## 具体设计

- 根目录 `vendor/nrc_interface/nrc_linux_x86_64`、`vendor/actuator/linkerhand-python-sdk/LinkerHand` 是 NRC/O6 唯一 SDK 来源；GELLO 的已修正采样时间戳代码只保留在根目录 `vendor/gello`。
- 连接端点、ServoJ 七轴向量和物理相机参数来自 `config/hardware/<profile>.toml`；GELLO 标定、映射、安全阈值、动作库和采集设置保留在 `config/teleop/gello_cr.json`。
- 集成的配置存储明确覆盖硬件 profile 拥有的字段，设置页将这些字段设为只读并标明来源。保存其他参数不会回写或改写硬件 TOML。
- 最终 Dataset 写入 `dataset/train/`，中断批次写入 `dataset/staging/`，命名轨迹写入 `dataset/replay/trajectories/`，日志写入 `logs/`。恢复和发布保留原有新 Segment、原子发布和防覆盖语义。
- 父项目工作流继续持有一个 NRC/手部会话。共享轨迹读取和有借用会话的 Player 适配器负责跨模块调用，借用适配器不连接、不上电、不关闭父会话。
- 共享轨迹读取支持 UUID Store、LeRobot V2.1/V3 和父项目 PTP 数据。TCP 增量动作不得被当成绝对关节角；PTP 的 mm 与轨迹模型的 m 显式转换；保留关节 mask 和离线计划不可直接执行等约束。
- 根项目的会话锁防止遥操界面和任务流同时占有同一机器人；锁只覆盖真实连接生命周期，不影响预览、配置、数据浏览和模型服务。
- `scripts/run_teleop.sh`、`scripts/setup_teleop_env.sh` 为根项目入口，使用 NRC Python 3.12 环境；Writer 保留独立解释器。现有部署 HMI 提供采集入口和共享轨迹任务。

## 并行实施归属

1. SDK/设备：共享 SDK 迁移、NRC 七轴限值、O6 命名空间隔离、设备会话锁、对应回归。
2. 轨迹互通：父项目共享 I/O/借用执行桥、replay/PTP/workflow/HMI 调用、语义兼容回归。
3. UI 接口：应用工厂与设置存储注入、profile 只读字段、Designer 保持不变、对应回归。
4. 根代理：集成配置存储、路径、入口、依赖说明、导入记录、跨模块集成与最终验证。

## 稳定性验证

使用已有隔离环境和内存设备；只新增能复现集成边界问题的功能回归，不增加哈希、像素匹配或冒烟框架。

- SDK 能从共享位置加载，O6 与父 `core` 模块共存；七轴限值按配置传递。
- 从任意工作目录启动，profile 与所有输出路径均指向父项目；设置保存和环境覆盖不改变共享硬件源。
- 真实临时 Parquet/元数据验证两向读取、TCP 动作含义、单位转换、V3 多 Episode 和命名轨迹约束。
- 多任务共用同一借用会话，停止/异常不会启动新连接；跨进程会话竞争可见拒绝，正常关闭释放。
- GELLO 原有离线套件、目标项目集成回归、Qt 实际离屏交互、V2.1/V3/HDF5 写入与中断恢复。
- 记录实际命令、结果及真机联调尚未执行的边界。

## 交付

完成后将稳定的新克隆放到远端持久目录，保留原工作区；提交集成分支和变更说明。若目标仓库推送权限不足，保留本地提交并交付可应用的分支/补丁，不覆盖远端主分支。

## 实施记录

- 共享 SDK、七轴 ServoJ 参数、会话互斥和失败关闭语义已完成。
- 轨迹读取、借用会话 Player、父工作流 trajectory 任务和部署 HMI 入口已完成。
- 父配置组合、只读硬件参数、根启动脚本和独立 Writer 环境安装入口已完成。
- 2026-10-17：原 GELLO 离线套件 924 通过，包含实际 V2.1/V3/HDF5 写盘与中断恢复；父会话/轨迹/HMI 13 通过；新增配置组合 15 通过。
- 最终完整离线回归 957 通过，Designer 重新生成后界面回归 73 通过；新克隆的正式 NRC/V2.1/HDF5 环境中 38 项实际写入、恢复和父集成验证通过。只读审查的旧 PTP 兼容及左右手地址问题已修复。未连接真实设备。
- 新克隆已移至远端 `/home/ubuntu/cyf/robot_learning_workbench-integrated-20261017`。历史 JSON 与备份在 `dataset/replay/legacy_gello` 保留，并只读转换为共享 UUID Store；不随代码提交。
