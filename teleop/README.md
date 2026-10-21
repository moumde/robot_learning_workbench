# GELLO 遥操与数据采集

以下命令都在父项目 `robot_learning_workbench/` 根目录运行，不在 `teleop/gello_cr/` 内运行。
遥操的界面、控制、设备适配和采集代码都在 `teleop/gello_cr/`；共用 SDK 放在父项目 `vendor/`。

## 首次安装

```bash
./scripts/setup_teleop_env.sh
./scripts/setup_gello_writer_env.sh v21  # 使用默认 V2.1 格式采集时安装
./scripts/run_teleop.sh --check-only
```

先在 `config/hardware/cr3_o6.toml` 核对机器人地址、O6 串口和相机序列号，
在 `config/teleop/gello_cr.json` 核对 GELLO 串口、标定和采集设置。
已有 HOME、标定和运动阈值需要按当前现场确认。

## 日常使用

```bash
./scripts/run_teleop.sh
```

窗口启动后处于 OFFLINE，不会自动连接设备或运动。在“数据采集”页依次操作：

1. 点“连接机器人”，确认机器人反馈正常。
2. 点“上使能”（Servo On），确认 Servo 状态。
3. 选择 GELLO，点“连接主臂 / O6”，确认遥操设备就绪。
4. 点“启动相机”，确认三路画面。
5. 在“任务与数据集”填写任务名称、任务描述和保存目录，点“创建数据集”。
6. 在页面底部固定操作栏点“开始采集”，同时启动遥操和 Episode 录制。
7. 完成操作后点“回 HOME 并成功保存”：HOME 接管遥操，回零过程继续录制，确认到位后保存成功 Episode，机器人保持停止。
8. 点“开始采集”进入下一段；全部结束后点“完成数据集”。退出前下使能并断开设备。

需要直接结束时，点“成功保存”或“失败保存”，停止当前遥操并保存；不保留则点“丢弃本段”。
独立“回 HOME”只接管运动，不结束 Episode；到位后可点“重新开始遥操”继续同一段录制。
HOME 失败或被停止/急停中断时不会自动成功保存；保存失败时保留待处理数据，界面提供后续处理。
单独“开始遥操”仍可用于不录制的调试；回放、精确走点采集需先启动对应运动来源。

“轨迹与走点”工作区共用左侧轨迹库，通过顶部模式切换“轨迹录制 / 轨迹回放 / 走点规划”。
录制模式中，“开始记录”同时启动遥操，“停止并保存”停止遥操并保存轨迹；“重试保存”只保存，不启动运动。
回放模式先选择轨迹并预览，在右侧确认速度、相对/绝对模式及 Arm/Hand，再明确开始回放。
走点模式编辑目标或路点，生成规划后再执行；“保存为轨迹”写入同一个轨迹库，可在回放模式选择使用。
切换模式不会启动运动；运动正在执行或录制结果未处理时，保留相应操作区，先完成或停止并处理数据。

走点规划中的“路径碰撞预检：未实现”是能力说明：当前未验证自碰撞或环境障碍物，
不能据此判定路径安全。实际规划或控制器错误会单独显示在预览顶部。

## 文件与排错

- 配置：父项目 `config/teleop/gello_cr.json`、`config/hardware/*.toml`。
- 完成的数据：`dataset/train/`；采集中及待恢复批次：`dataset/staging/`。
- 保存的轨迹：`dataset/replay/trajectories/`。
- 运行和失败日志：自动写入父项目 `logs/teleop.log`，包含启动及命令失败的异常堆栈。

操作失败后先看界面提示，再在父项目根目录查看日志末尾的对应时间、命令和异常：

```bash
tail -n 150 logs/teleop.log
```

未完成的数据按 [恢复说明](../docs/teleop/dataset.md) 处理。
安装和环境细节见 [集成说明](../docs/gello_cr_integration.md)，
代码目录见 [模块说明](gello_cr/README.md)，维护细节见 [架构](../docs/teleop/architecture.md)、
[配置](../docs/teleop/configuration.md)及 [硬件](../docs/teleop/hardware.md)。
