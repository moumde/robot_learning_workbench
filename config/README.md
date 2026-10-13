# config/

这里放运行时硬件 profile 和配置中间层。

- `hardware/`：每套机器人系统/工位一份 TOML profile；当前默认配置为 `hardware/cr3_o6.toml`；
- `hardware.py`：读取、校验 TOML，并将配置转换为 `vendor/` 适配层的构造参数。

程序优先使用：

```python
from config.hardware import load_hardware_config

hardware = load_hardware_config()
robot = hardware.create_nrc_interface()
cameras = hardware.create_d435_interface()
hand_kwargs = hardware.hand.api_kwargs()
```

新增工位或更换设备组合时，复制并命名 profile，例如 `hardware/cr3_o6_lab_b.toml`、`hardware/cr5_o6_lab_a.toml`。通过 `load_hardware_config(path)` 或程序的 `--config` 选择配置。若配置包含不应共享的现场信息，应放在本机私有路径并避免提交账号、密钥等敏感信息。

