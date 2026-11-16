"""Prepare optional GELLO dependencies before opening the operator UI."""

from __future__ import annotations

import shutil
import subprocess
import sys

_MISSING_SDK = 42
_PROBE = """\
try:
    from dynamixel_sdk.group_sync_read import GroupSyncRead
    from dynamixel_sdk.group_sync_write import GroupSyncWrite
    from dynamixel_sdk.packet_handler import PacketHandler
    from dynamixel_sdk.port_handler import PortHandler
    from dynamixel_sdk.robotis_def import COMM_SUCCESS, DXL_HIBYTE, DXL_HIWORD, DXL_LOBYTE, DXL_LOWORD
except ModuleNotFoundError as exc:
    if exc.name == 'dynamixel_sdk':
        raise SystemExit(42)
    raise
"""


def ensure_dynamixel_sdk() -> None:
    """Install a missing SDK into the interpreter running this application."""
    python = sys.executable
    guidance = f"Python: {python}\n请检查网络和 Python 环境，或运行 ./scripts/setup_teleop_env.sh。"

    def probe():
        try:
            return subprocess.run(
                [python, "-c", _PROBE],
                capture_output=True,
                text=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"无法检查 Dynamixel SDK: {exc}\n{guidance}") from exc

    result = probe()
    if result.returncode == 0:
        return
    if result.returncode != _MISSING_SDK:
        raise RuntimeError(f"Dynamixel SDK 导入失败，请修复已有环境：\n{result.stderr}\n{guidance}")

    uv = shutil.which("uv")
    command = (
        [uv, "pip", "install", "--python", python, "dynamixel-sdk"]
        if uv
        else [python, "-m", "pip", "install", "dynamixel-sdk"]
    )
    print(f"Dynamixel SDK 缺失，正在为 {python} 安装 dynamixel-sdk…", flush=True)
    try:
        installed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Dynamixel SDK 安装未完成：{exc}\n{guidance}") from exc
    if installed.returncode != 0:
        raise RuntimeError(
            f"Dynamixel SDK 自动安装失败：\n{installed.stdout}\n{installed.stderr}\n{guidance}"
        )
    result = probe()
    if result.returncode != 0:
        raise RuntimeError(f"安装后仍无法导入 Dynamixel SDK：\n{result.stderr}\n{guidance}")
    print("Dynamixel SDK 已安装并通过导入检查。", flush=True)
