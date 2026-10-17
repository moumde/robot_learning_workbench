# 架构与生命周期

v1.0 采用一个正式 HMI、一个应用命令入口和一个运动仲裁器。页面只提交命令和显示快照；设备 SDK、运动执行和 Dataset Writer 均不由页面直接调用。正式入口是 `scripts/run_operator.sh`，启动保持 OFFLINE / IDLE。

## 依赖与权威状态

```text
ui → app / core
bootstrap → app + devices + recording + ui（组合根）
app → control + motion + trajectory + recording + devices
motion → 执行器 / 设备适配接口
trajectory → 模型 / Store / Recorder / Planner / Player → motion
recording → CaptureFrame / Session → 独立 Worker → 格式 Writer
devices → vendor SDK / 串口 / 网络
```

`ApplicationService` 串行分发普通命令，`WorkflowStateMachine` 管理转换，`app/permissions.py` 结合缓存设备状态、Episode 和 Dataset 快照判断许可并给出拒绝原因；STOP、FAULT、ESTOP 可以优先抢占普通操作。HMI 的按钮、快捷键和菜单使用相同命令策略，不另存一份许可状态。`TeleopRuntime` 保留应用 Facade，具体工作由 `TeleopService`、`HomeService`、`HandActions`、`TrajectoryService`、`CaptureSnapshot` 和 `PointMotionService` 承担。

## UI 边界

`ui/forms/` 的八份 Designer 表单维护主窗口、采集、轨迹、规划、数据集、机器人状态、设置和恢复面板的静态布局；`scripts/generate_ui.py` 生成 `ui/generated/`。`ui/styles/app.qss` 使用 role/state 属性统一样式。设置中的配置字段和规划表格行按 schema/数据动态生成。

MainWindow 负责导航、命令通道和一次 Presenter poll；同一 UiFrame 分发给全部页面。CollectionPage 绑定表单与信号，CollectionController 负责步骤提示、表单锁定、结果选择和保存回执；CameraPreviewRenderer 负责缓存图像转换，status_presenter 负责跨页状态和错误横幅。UI 不直接调用 SDK 或 Writer。

`RobotDescriptor` / `RobotCapabilities` 描述身份、末端和操作能力，由 bootstrap 的真实硬件注册提供。现在只有 CR3A + O6 实现；新增机器人仍需实现现有设备/运动学接口并在组合根注册，不需要复制采集页。六轴规划编辑器和当前硬件构建器尚不代表任意自由度机器人即插即用。

Servo 状态来自 Cr3aLifecycle 的受管反馈缓存；读取 UI 快照不触发 SDK 查询。HOME 不自动上使能，不在遥操/录制/Pending/故障期间接管运动。录制来源显式选择 teleop/replay/point_move，Finish 由一个后台命令停止采样并保存，保存失败保留 Pending。相机失联或过期停止采样并留下错误，丢帧未知时不伪造为零。

| 状态或资源 | 权威拥有者 | 含义 |
| --- | --- | --- |
| 操作流程、命令许可、FAULT / ESTOP | `ApplicationService` / `WorkflowStateMachine` | 普通命令完成后仍须核对抢占代次，不能覆盖安全状态 |
| 运动权、当前控制源、已接受目标 | `MotionCoordinator` / lease | Teleop、HOME、回放、规划、Policy 共用同一执行出口 |
| 机器人连接、主臂和手 | bootstrap / `ConcreteRuntime` 与设备适配器 | 设备打开和关闭由生命周期层管理 |
| Episode、Pending、批次、恢复 | Recording Session / Batch | 运动结束不会自动判定 Episode 成功 |
| 轨迹录制、待保存轨迹、回放 | `TrajectoryService` / Recorder / Player | 轨迹保存与 Dataset Writer 分离 |
| 窗口显示、预览缓存 | Presenter / ViewModel | 显示状态不是设备控制权 |

## 线程和进程归属

| 执行上下文 | 拥有者与工作 | 停止责任 |
| --- | --- | --- |
| Qt 主线程 | MainWindow、页面、Presenter 消费事件与显示快照 | 资源关闭成功后才结束 Presenter |
| 命令后台执行 | CommandPort / ApplicationService，避免 GUI 被连接或保存阻塞 | 先拒绝新命令，再等待已有命令结束 |
| 运动生产者 | Runtime 的跟随、HOME、回放及规划执行 | 设置停止事件，撤销 lease，等待线程退出 |
| 完成通知任务 | RuntimeBindings 的 `BackgroundJobs` | 运动完成回调异步提交流程事件，退出时有界等待，防止 STOP 与回调锁反转 |
| 设备反馈和相机轮询 | 对应设备适配器、`CameraPollingService` | 停止采样后关闭；超时作为可见错误返回 |
| Episode 采样 | Recording Session | 按配置采样周期运行，与 GUI 刷新周期独立 |
| 格式 Worker 子进程 | Recording WorkerClient | 负责 LeRobot / HDF5 导入、写入、合并、校验，最后关闭 |

`BackgroundJobs` 保存其启动的线程引用，关闭后拒绝新任务，并在截止时间内 join。超时会报告未退出任务；daemon 标记不等于允许忽略关闭失败。

## 安全边界与退出

连接不使能，使能不启动跟随；复位不恢复先前运动。STOP 撤销运动权并保持停止。F12 是软件紧急停止，控制柜物理急停仍需独立现场验收。设备反馈、SDK 提交和机器人实际到位是不同证据；规划执行另检查真实反馈到位。

退出前先处理 Partial、未保存 Episode 和轨迹。正常关闭顺序由 `OperatorApplication.close()` 组织：拒绝新命令 → 停止 Episode 采样 → 停止运动生产者 → 排空命令与完成通知 → 关闭 DAgger → 明确保存待处理内容（若选择保留，则未完成 Episode 记为 Failure）→ 相机 → Runtime 的主臂、手、机器人 → Recording Worker → Presenter。运行时负责机器人停止、下使能及断开。

关闭成功的资源会登记；失败汇总为 `ExceptionGroup`，保留错误并允许再次关闭时重试失败资源。采样、运动生产者或任务排空失败时，保留其依赖设备和 Writer；相机轮询未退出时也不先释放流。相机发现任务超时仍会尝试停止应用，并保留发现错误。任何关闭或 Worker 失败都不能被当作保存成功。现场断连、物理急停和退出行为仍须按 [发布清单](release_v1.md) 验收。
