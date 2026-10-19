# Robot Learning Workbench — TrainUI

TrainUI 是 `robot_learning_workbench` 中用于 **OpenPI / π0 / π0.5 训练配置管理与训练启动** 的桌面图形界面。

当前版本重点解决：

- 从 OpenPI 注册表读取训练配置；
- 启动时只读取配置名称，避免一次性解析全部配置；
- 用户选择某个配置后，只解析当前选中的 `TrainConfig`；
- 显示模型、数据配置、学习率、优化器、Action Horizon 等信息；
- 读取本地 LeRobot 数据集；
- 计算 / 检查 `norm_stats`；
- 启动 OpenPI 训练；
- 实时显示训练进度、Loss、Gradient Norm、Parameter Norm 和 GPU 状态；
- 保留 OpenPI 原始配置作为最终训练依据。

## 1. 项目结构

```text
robot_learning_workbench/
├── hmi/
│   └── trainui/
│       ├── app.py
│       ├── controller.py
│       ├── models.py
│       ├── paths.py
│       ├── styles.py
│       ├── bridge/
│       ├── services/
│       ├── views/
│       ├── widgets/
│       └── tests/
├── module/
│   ├── openpi/
│   │   └── .venv/
│   └── nrc/
│       └── .venv/
└── scripts/
    ├── run_openpi.sh
    ├── run_trainui.sh
    └── setup_nrc_env.sh
```

## 2. 环境说明

TrainUI 使用两个独立 Python 环境。

### TrainUI / PySide6

```text
module/nrc/.venv
```

主要用于 GUI、PySide6、Controller、Services。

### OpenPI

```text
module/openpi/.venv
```

主要用于 OpenPI、JAX、LeRobot、π0 / π0.5、Norm Stats 和训练。

TrainUI 不直接在 GUI Python 进程中加载 OpenPI，而是通过：

```bash
scripts/run_openpi.sh
```

启动独立 OpenPI 子进程，以避免 Qt、Python 版本和 `LD_LIBRARY_PATH` 冲突。

## 3. 启动 TrainUI

```bash
cd ~/robot_learning_workbench
git switch feature/train
chmod +x scripts/run_trainui.sh scripts/run_openpi.sh
./scripts/run_trainui.sh
```

如果不需要切分支，可省略 `git switch feature/train`。

## 4. Config Lazy Loading

TrainUI 当前采用按需加载：

```text
启动 TrainUI
   ↓
只读取 OpenPI 配置注册表中的名称
   ↓
下拉框显示全部 config
   ↓
不解析全部 TrainConfig
   ↓
用户选择一个 config
   ↓
只解析当前 config
```

启动后应看到：

```text
正在读取 OpenPI 配置名称…
已读取 OpenPI 配置名称；尚未解析详细配置。
```

选择例如：

```text
pi05_piper_lora_h30
```

之后才解析其：

```text
Pi0Config
LeRobotPiperDataConfig
RepackTransform
action_dim
action_horizon
batch_size
num_train_steps
optimizer
lr_schedule
weight_loader
norm stats
checkpoint path
```

## 5. 单独检查 OpenPI 配置名称

```bash
cd ~/robot_learning_workbench

./scripts/run_openpi.sh python -m hmi.trainui.bridge.inspect_openpi --names
```

正常应输出：

```text
TRAINUI_JSON=[
  "pi0_aloha",
  "pi05_aloha",
  ...
  "pi05_piper_lora_h30",
  "pi05_piper_lora",
  ...
]
```

## 6. 配置来源

TrainUI 不再写死 CR3、Piper、Aloha、DROID、LIBERO 等机器人。

OpenPI 注册的 `TrainConfig` 是唯一配置来源。只要新配置已经注册到 OpenPI config registry，TrainUI 就应能显示它。

## 7. 数据集

默认本地数据集根目录：

```text
~/robot_learning_workbench/dataset/train
```

典型 LeRobot 数据结构：

```text
dataset/train/
└── three_stack/
    ├── meta/
    │   └── info.json
    ├── data/
    ├── videos/
    └── ...
```

关键文件：

```text
meta/info.json
```

如果配置中：

```python
repo_id="three_stack"
```

则本地应存在：

```text
dataset/train/three_stack/meta/info.json
```

否则 OpenPI 可能尝试将 `three_stack` 当作 Hugging Face 数据集仓库查询。

## 8. Dataset Contract

TrainUI 会尽量从当前 DataConfig 的 `RepackTransform` 自动推导数据集所需字段，而不是按机器人名称硬编码。

例如某些 Piper 配置可能需要：

```text
observation.images.front
observation.images.wrist
observation.state
action
```

而其他机器人配置可能要求不同字段。

## 9. Norm Stats

对于支持 LeRobot Norm Stats 的配置，可以在 UI 中计算归一化统计。

如果数据集不存在，例如：

```text
dataset/train/three_stack/meta/info.json
```

缺失，应先检查数据集，而不是继续计算。

检查命令：

```bash
find ~/robot_learning_workbench/dataset/train   -path '*/meta/info.json'   -print
```

## 10. 训练

TrainUI 最终调用 OpenPI 官方训练入口。

桥接代码位于：

```text
hmi/trainui/bridge/run_training.py
```

UI 中的参数只覆盖当前配置实际支持的字段；OpenPI `TrainConfig` 仍是最终训练依据。

## 11. 训练监控

TrainUI 支持显示：

```text
训练进度
Loss
Gradient Norm
Parameter Norm
GPU 状态
Checkpoint 状态
训练日志
```

OpenPI tqdm 输出例如：

```text
Progress on: 3.00it/10.0it
```

会被用于 GUI 进度条。

## 12. 测试

```bash
cd ~/robot_learning_workbench

python -m compileall -q hmi/trainui

PYTHONPATH=. python -m pytest hmi/trainui/tests -q

bash -n scripts/run_trainui.sh
bash -n scripts/setup_nrc_env.sh
```

## 13. 常见问题

### Git 提示作者身份未知

```bash
git config user.name "YOUR_GITHUB_USERNAME"
git config user.email "YOUR_EMAIL"
```

### GitHub 不接受账号密码

GitHub HTTPS Git 操作不再使用普通登录密码。建议：

```bash
gh auth login
gh auth setup-git
```

然后：

```bash
git push
```

### Qt / xcb 报错

```bash
sudo apt install libxcb-cursor0
```

并确认 GUI 使用：

```text
module/nrc/.venv
```

### OpenPI 找不到数据集

```bash
find dataset/train -path '*/meta/info.json' -print
```

确认 UI 里选择的数据集实际存在。

### Hugging Face 404

如果出现：

```text
RepositoryNotFoundError
```

通常表示本地数据集不存在，OpenPI 又尝试按远程 repo 查询。优先检查：

```text
dataset/train/<repo_id>/meta/info.json
```

## 14. Git 分支

建议 TrainUI 功能放在独立分支，例如：

```text
feature/train
```

查看当前分支：

```bash
git branch --show-current
```

提交：

```bash
git add hmi/trainui
git add scripts/run_trainui.sh
git add scripts/setup_nrc_env.sh

git commit -m "feat(trainui): add config-driven lazy loading and persistent inspector"
```

推送：

```bash
git push -u origin feature/train
```

注意先检查：

```bash
git remote -v
```

如果 `origin` 指向原作者仓库，push 会尝试推送到原作者仓库；如果使用自己的 fork，应把 `origin` 指向自己的仓库。

## 15. 推荐使用流程

```text
1. 启动 TrainUI
2. 选择 OpenPI Config
3. 检查完整配置
4. 选择训练数据集
5. 检查 Dataset Contract
6. 检查 / 计算 Norm Stats
7. 设置 Experiment Name
8. 检查训练参数
9. 启动训练
10. 观察 Loss / Progress / GPU
11. 检查 Checkpoint
```

## 16. 设计原则

1. OpenPI Config 是唯一真源；
2. 不按机器人名称硬编码；
3. 只加载当前选择的配置；
4. GUI 与 OpenPI 环境隔离；
5. 不修改 OpenPI 原始训练逻辑；
6. 数据字段从 DataConfig / RepackTransform 推导；
7. 配置不支持的参数不强制覆盖；
8. 训练最终由 OpenPI 自身执行；
9. 尽量在 GUI 层提前发现数据错误；
10. dataset、checkpoint、运行日志不应作为源码提交。

## 17. 当前版本

当前 TrainUI 版本：

```text
v1.6
```

主要变化：

```text
- Config 名称轻量读取
- 当前 Config 按需解析
- OpenPI Inspector 常驻子进程
- 全 Config Registry 支持
- Config Details 查看
- Config-driven Dataset Contract
- Dataset / Norm Stats 预检
- OpenPI 子进程环境隔离
- 中文训练界面
- tqdm Progress 解析
- Loss / Gradient / Parameter 曲线
```

## 18. License

TrainUI 属于 `robot_learning_workbench` 项目的一部分。

具体 License 以仓库根目录中的原始 License 文件为准。
