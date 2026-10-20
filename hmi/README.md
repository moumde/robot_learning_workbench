# HMI

`collection/` 为父级遥操与数据采集控制台，启动 `./scripts/run_teleop.sh`；`deploy/` 保留部署与任务工作流控制台。采集界面布局由 `collection/forms/` 的 Qt Designer `.ui` 维护，修改后运行 `module/nrc/.venv/bin/python scripts/generate_collection_ui.py`。共享架构见 [父级框架](../docs/parent_workbench_framework.md)。

基于 PySide6 的 CR3/O6 桌面控制台。它读取 `config/hardware/` 下的硬件 profile，
可启动/停止 OpenPI policy server，并管理 PI05 推理、完整 LeRobot 数据集重播和 CR3 走点轨迹重播任务。

首次安装或更新 NRC 环境以安装 PySide6：

```bash
./scripts/setup_nrc_env.sh
```

启动界面：

```bash
./scripts/run_deloy_hmi.sh
```

策略列表直接读取 `module/openpi/src/openpi/training/config.py` 中使用 `LeRobotCR3O6DataConfig` 的已注册 `TrainConfig.name`。选择策略配置后，界面从 `checkpoints/<配置名>/` 中列出训练实验（`exp-name`）；默认优先选中与策略配置同名的实验（如果存在），否则选择最近更新的实验。第二个下拉框列出该实验中的数值 checkpoint，默认选最大值，也可手动选择其他步数。可单独启动模型服务；
任务列表支持添加、删除、排序，并将当前任务流保存/读取为 `tasks/` 下的 JSON 配置。添加任务后，表单只显示所选任务类型需要的参数。走点任务会按编号顺序播放数据集中的全部 Episode，可选择关节空间或 TCP 空间，以及重复次数和速度倍率；TCP 重播会在运行时通过 CR3 接口做逆运动学转换。执行计划预览只检查配置和轨迹文件，
真实执行必须勾选运动确认，并在二次确认对话框中确认。

安全与当前限制：

- 模型服务启动和机器人运动是分开的；启动服务不会让机器人运动。
- 推理任务必须设置最长时长。当前策略接口没有任务完成信号，不会自动判断语义上的成功。
- 重播任务选择数据集根目录（应包含 `data/chunk-*/episode_*.parquet`），默认目录为 `dataset/replay/teleop_once`。程序按 episode 编号顺序播放全部轨迹，“完整数据集播放次数”表示重复整套轨迹序列的遍数。
- 走点任务默认使用 `dataset/replay/ptp_rectangle_v21`，按 episode 编号顺序重播其中全部轨迹；“关节空间”使用 `action` 前六维，“TCP 空间”使用 `target.tcp_pose` 并在线转换为关节目标。每条轨迹开始前会平滑移动到该轨迹首个关节点，走点模式不连接、不控制 O6。
- 界面把整条任务列表交给一个工作流进程；硬件只连接/上电一次，ServoJ 在任务间保持活动。每一遍数据集重播前会回到统一初始位姿，再限速移动到首条 episode 的首帧；同一遍内 episode 之间限速平滑过渡。完整工作流结束后才统一清理。
- 每个任务结束后都会检查伺服状态。若控制器进入错误态，工作流停止，不会继续下一个运动任务；此时先检查并清除控制器报警，不要绕过保护继续执行。
- 如果工作流启动前控制器已经处于 `SERVO_ERROR`，程序会拒绝自动清错或上电；先在控制器侧确认故障原因并人工复位。
- “停止当前任务”会发送中断信号，让脚本有机会执行硬件清理；若 15 秒仍未退出，界面不会强制杀掉任务进程。它不等同于控制柜急停，操作员必须始终能够使用实体急停。
- 模型服务进程由界面单独管理。关闭界面时会询问是否停止运行中的任务/服务。
