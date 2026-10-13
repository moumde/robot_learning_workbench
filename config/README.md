# config/

这里放运行时硬件配置和配置中间层。

- `hardware.toml`：NRC、LinkerHand、D435 的现场连接与规格配置；
- `hardware.py`：读取、校验 TOML，并将配置转换为 `vendor/` 适配层的构造参数。

程序优先使用：

```python
from config.hardware import load_hardware_config

hardware = load_hardware_config()
robot = hardware.create_nrc_interface()
cameras = hardware.create_d435_interface()
hand_kwargs = hardware.hand.api_kwargs()
```

现场机器需要不同 IP、串口或相机序列号时，复制 `hardware.toml` 到本机私有路径，并通过 `load_hardware_config(path)` 或测试程序的 `--config` 使用。不要把账号、密钥等敏感信息写入被提交的配置文件。

