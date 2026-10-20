# 父级 Workbench 统一运行与设备框架

用户目标：Qt UI、状态机、遥操运行时、Recorder，以及机器人与相机适配/通信管理真正属于 robot_learning_workbench 父项目。现有 teleop/gello_cr 保留设备输入、GELLO 控制映射与兼容入口。

## 边界

- core/workbench：app、core、motion、trajectory、recording、bootstrap、共享 geometry、配置/日志/诊断/数据契约。
- core/hardware：CR3A、NRC 会话适配、O6 单线程通信、相机组与原生 RGB 采样后端、通用相机配置。
- hmi/collection：真实 Qt 窗口、页面、Controller、.ui、生成绑定、QSS，与 hmi/deploy 并列。
- teleop/gello_cr：GELLO 设备、控制策略、映射、校准和兼容入口；其他已有主设备保持支持。
- 已有 gello_cr 导入暂保留叶模块兼容层，指向同一个父级类，避免双份状态机/数据类型。实现只保留父目录的一份。

## 真实通信复用

CR3A 适配层持有一个父 CR3Interface；socket、ServoJ、读取与普通目标发送均由该实例管理。补充父类缺少的能力，保留 mode/servo 等待、4098、robot_num、MoveJ、HOME、停止与断线语义。rad/deg 仅在原接口适配边界转换，外部轴原样保留。只由父会话持有端点锁。

相机复用一个父 CR3O6CameraInterface 管理三相机。UI 环境使用共享原生 RGB 后端，避免强制安装训练/LeRobot 环境。获取到新物理帧时才更新时间戳；视图读取缓存不制造新时间戳。父部署默认 read/read_raw 行为保持；一个物理相机只有一个采样者。

O6 现有可靠 worker 与恢复队列迁到父级，继续组合父 vendor 的 LinkerHandO6RS485。保留目标去重、故障反馈、取消与 hold 行为。

## 不变量与范围

保留未提交的 HOME/断线恢复/解释器路径修复。启动 OFFLINE，不自动连接、使能、运动；恢复不自动跟随；Recording 锁定配置与设备。安全阈值、现有数据维度、格式和字段不变。保留 .ui/QSS，禁止修改训练和 policy 推理实现，不进行大规模驱动重写。

配置继续使用父 config/hardware 与 config/teleop；数据继续写 dataset/train、dataset/staging、dataset/replay。core/trajectory_bridge 直接依赖父公共轨迹模块。原启动方式兼容，正式入口为父 hmi/collection。

## 验收

父包直接导入不依赖 gello_cr 路径注入；兼容导入类型相同。真实调度链路经过父机器人和相机实例。实际 writer 子进程从其他 cwd 可读写三格式数据。完成父入口的模拟联通、故障恢复及持续采集测试，统计 FPS/质量/GUI 响应/退出资源。只做必要回归与实际流程测试，不新增哈希匹配或大量防御性测试。
