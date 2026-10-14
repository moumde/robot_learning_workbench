# tasks/

这里放置工作台自身的训练任务、业务流程和部署任务定义。

HMI 保存的推理/轨迹重播工作流为 JSON，放在此目录下；可通过界面中的“保存工作流”和“读取工作流”管理，文件记录任务顺序、推理指令/时长，以及数据集路径、控制空间、播放次数和速度倍率。项目内数据集以相对仓库根目录的路径保存，便于在同一项目布局中迁移。轨迹任务支持完整 LeRobot 数据集重播和 CR3 走点轨迹重播（按编号顺序播放全部 Episode，关节空间或 TCP 空间）。

硬件 profile 放在 `config/hardware/`，当前 CR3/O6 工位配置为 `config/hardware/cr3_o6.toml`，统一加载入口是 `config/hardware.py`。OpenPI 原生训练配置位于 `module/openpi/src/openpi/training/config.py`，不需要复制到这里。

建议按任务或流程拆分文件，例如：

```text
tasks/
├── README.md
├── workflow.json
├── collect_cr3_o6.toml
├── train_cr3_o6.toml
└── deploy_cr3_o6.toml
```
