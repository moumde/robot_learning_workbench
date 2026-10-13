# tasks/

这里放置工作台自身的训练任务、业务流程和部署任务定义。

硬件 profile 放在 `config/hardware/`，当前 CR3/O6 工位配置为 `config/hardware/cr3_o6.toml`，统一加载入口是 `config/hardware.py`。OpenPI 原生训练配置位于 `module/openpi/src/openpi/training/config.py`，不需要复制到这里。

建议按任务或流程拆分文件，例如：

```text
tasks/
├── README.md
├── collect_cr3_o6.toml
├── train_cr3_o6.toml
└── deploy_cr3_o6.toml
```
