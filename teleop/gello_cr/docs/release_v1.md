# v1.0 发布准备与验收

软件版本为 **1.0.0**。当前状态是 **发布准备，真机验收未签收**。2026-10-17 按用户要求将整体结构优化交付到新分支 `codex/workbench-structure-cleanup-20261017`；不创建版本 tag，不发布正式 Release，不上传采集数据或操作硬件。离线回归证明软件约束，不能作为现场安全或采集性能的证据。

## 离线验证记录（2026-10-17）

在远端 Ubuntu 当前工作副本执行：

```bash
/tmp/gello-cr-refactor-venv/bin/python -m compileall -q src scripts tools examples
/tmp/gello-cr-refactor-venv/bin/ruff check src scripts tools examples
/tmp/gello-cr-refactor-venv/bin/ruff format --check src scripts tools examples
GELLO_TEST_V21_PYTHON=/tmp/gello-v21-test-env/bin/python \
GELLO_TEST_V3_PYTHON=/tmp/gello-v3-test-env/bin/python \
/tmp/gello-cr-refactor-venv/bin/python -m pytest -q --tb=short
git diff --check
```

| 检查 | 已观察结果 | 适用范围 |
| --- | --- | --- |
| compileall / Ruff check / Ruff format | 通过，136 个生产 Python 文件格式检查 | 最近源码静态检查；临时环境路径只用于本次验证 |
| 两个官方 LeRobot 环境完整回归 | **834 passed、无跳过，74.20s** | 当前完整工作区重跑，包含 V2.1 / V3 / HDF5、硬件反馈新鲜度及 HMI 回归 |
| 生命周期补充回归 | 本次关闭顺序修复后 41 项相关测试通过 | 停采样、停止运动、排空任务失败时保留依赖并可重试，以及相机退出阻塞场景 |
| 一次性轨迹迁移 | 四个 legacy JSON 均能转换到临时 TrajectoryStore | 不改源数据，临时输出已清理 |
| 只读诊断 | `version=1.0.0`、`hardware_profile=cr3a_o6`、`connected_devices={}` | 软件身份；没有证明硬件连接 |

最终修复后的静态检查和 `git diff --check` 均通过；本表测试命令中的临时解释器路径仅是本次环境记录。较早的 693 / 695 / 703 / 721 测试快照不作为本轮最终结果。CI 仅做离线 compileall、Ruff、pytest 和 diff 检查；默认排除 `hardware`，缺少官方 Worker 环境时会明确跳过相应测试，不应把跳过等同通过。

## 现场签收清单

由现场操作者记录设备、固件、SDK、配置副本、日期、结果及证据路径，逐项签字。以下项目目前均未签收：

- [ ] 启动保持 OFFLINE；连接不使能，使能不跟随，切页不运动。
- [ ] GELLO 六关节方向、偏置、倍率、夹爪/O6 方向和 HOME 与现场一致；可选控制模式单独验收。
- [ ] STOP、F12 软件急停和控制柜物理急停实际停止运动；复位不自动续动、续播或续录。
- [ ] 机器人/主臂/手/相机断连、反馈过期和 Worker 故障可见，不自动重连继续运动。
- [ ] Teleop、HOME、相对/绝对回放、Arm/Hand 选择、Joint/TCP/Waypoint 规划共用仲裁，实际反馈到位检查有效。
- [ ] 三路画面对应正确序列号和 ROI；完成 Success / Failure / 丢弃，三种格式均导出并校验。
- [ ] 中断后明确处理 Partial，恢复到新 Segment，合并输出连续索引且保留原 journal。
- [ ] 采样、回放和相机发现期间退出：先停止生产者再释放依赖；超时可见、待处理数据保留、重试关闭有效。
- [ ] 关闭前未保存 Episode / 轨迹有明确选择；退出停止、下使能、断连与 Worker 回收均得到反馈确认。
- [ ] 连续遥操作至少 30 分钟，记录控制周期、反馈 Age、跟踪误差和资源占用，无意外运动或后台任务累积。
- [ ] 完成至少 50 条 Episode，优先现场主要 V3 格式；条件允许时补充 V2.1 / HDF5，验证保存、丢弃、合并与正式校验。
- [ ] 完成至少 20 次轨迹录制 / 回放 / STOP 循环，核对运动 Owner、线程及 Worker 进程均正确回收。
- [ ] 演练进程中断 → Partial 决策 → 恢复 → 重复中断/恢复 → finalize，核对新 Segment、连续索引、来源追溯和原数据保留。

## 性能实测表（待填）

| 项目 | 当前配置目标 | 实测与条件 |
| --- | --- | --- |
| GELLO 反馈 | 100 Hz | 待测：平均/P95 周期、丢帧，运行时长 |
| Teleop | `period_s=0.05`，20 Hz | 待测：控制周期与延迟分布、跟踪误差 |
| Dataset | 20 FPS，480×640 RGB | 待测：实际 FPS、迟帧率、最大间隔、存储负载 |
| 相机缓存桥接 | 30 Hz 轮询 | 待测：每路 FPS、Age / Skew P95 和最大值 |
| GUI | 100 ms，10 Hz 刷新 | 待测：交互延迟、CPU / RSS、长时稳定性 |
| 停止与退出 | 无现场实测 | 待测：STOP 至实际停止时间、正常/故障退出时间 |

配置目标不是实测值。软件还未提供经现场认可的绝对关节与工作空间限值；NRC IK 当前只有单解，TCP 规划无法保证覆盖所有分支；DAgger 外部模型接口需独立部署联调。完成上述验收和最终离线回归后，再由维护者决定发布与版本标记。
