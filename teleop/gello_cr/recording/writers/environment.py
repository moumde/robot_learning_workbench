"""Prepare only the selected independent dataset writer environment."""

import os
import platform
import shutil
import signal
import subprocess
from pathlib import Path

from ..errors import WriterError
from ..formats import DatasetFormat


def _repository_root():
    return Path(__file__).resolve().parents[4]


def _setup_help(format_name):
    if format_name == DatasetFormat.LEROBOT_V21:
        return (
            "默认 V2.1 环境安装命令：./scripts/setup_gello_writer_env.sh v21。"
            "自定义解释器请安装匹配的 SDK，或修改 dataset.worker_pythons.lerobot_v21。"
        )
    if format_name == DatasetFormat.LEROBOT_V3:
        return (
            "V3 需要已验证源码；设置 GELLO_V3_LEROBOT_SPEC 后运行 "
            "./scripts/setup_gello_writer_env.sh v3，或修改 dataset.worker_pythons.lerobot_v3。"
        )
    return (
        "HDF5 环境安装命令：./scripts/setup_teleop_env.sh；"
        "自定义解释器请安装 h5py，或修改 dataset.worker_pythons.hdf5。"
    )


def _probe_code(format_name):
    if format_name == DatasetFormat.HDF5:
        return "import h5py"
    code = "from lerobot.datasets.lerobot_dataset import CODEBASE_VERSION, LeRobotDataset\n"
    if format_name == DatasetFormat.LEROBOT_V21:
        return code + "assert CODEBASE_VERSION == 'v2.1', 'Expected LeRobot V2.1 (lerobot==0.3.3)'"
    if format_name == DatasetFormat.LEROBOT_V3:
        return code + (
            "import inspect\n"
            "from lerobot.configs.video import RGBEncoderConfig\n"
            "required = {'rgb_encoder', 'streaming_encoding', 'encoder_queue_maxsize', 'encoder_threads'}\n"
            "assert CODEBASE_VERSION.startswith('v3.'), 'Expected LeRobot V3'\n"
            "assert required <= set(inspect.signature(LeRobotDataset.create).parameters), "
            "'V3 lacks streaming encoder API'\n"
            "RGBEncoderConfig(vcodec='h264', pix_fmt='yuv420p', crf=18, preset='fast', g=20)\n"
        )
    raise WriterError(f"不支持的数据集格式：{format_name}")


def _install_default_v21(command, *, cwd):
    """Bound the whole Linux setup process tree, including uv and its pipes."""
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=1800)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def prepare_writer_environment(
    format_name, python_executable, *, event_callback=None, allow_install=True
):
    """Check the SDK; bootstrap a missing default Linux V2.1 environment only."""
    # A venv's bin/python is commonly a symlink. Keep its entry path so Python
    # finds that venv's pyvenv.cfg and installed packages.
    python = Path(os.path.abspath(Path(python_executable).expanduser()))
    repo_root = _repository_root()
    default = repo_root / "module/gello_writers/v21/.venv/bin/python"
    guidance = f"格式：{format_name}；Python：{python}\n{_setup_help(format_name)}"
    options = dict(
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if not python.is_file():
        can_prepare = (
            allow_install
            and format_name == DatasetFormat.LEROBOT_V21
            and python == default
            and not python.is_symlink()
            and platform.system() == "Linux"
            and shutil.which("uv")
        )
        script = repo_root / "scripts/setup_gello_writer_env.sh"
        bash = shutil.which("bash") if can_prepare else None
        if not can_prepare or not bash or not script.is_file():
            raise WriterError(f"数据集 Writer Python 不存在；尚未开始采集。\n{guidance}")
        if event_callback:
            event_callback(
                "info", "正在首次准备 V2.1 数据集环境（含 CPU PyTorch），可能需要数分钟；请等待。"
            )
        try:
            installed = _install_default_v21([bash, str(script), "v21"], cwd=repo_root)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WriterError(f"V2.1 环境自动准备未完成：{exc}\n{guidance}") from exc
        if installed.returncode != 0 or not python.is_file():
            raise WriterError(
                f"V2.1 环境自动准备失败：\n{installed.stdout}\n{installed.stderr}\n{guidance}"
            )
        if event_callback:
            event_callback("info", "V2.1 数据集环境安装完成，正在检查 Writer SDK。")
    try:
        result = subprocess.run(
            [str(python), "-c", _probe_code(format_name)], timeout=60, **options
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WriterError(f"数据集 Writer 环境检查失败：{exc}\n{guidance}") from exc
    if result.returncode != 0:
        raise WriterError(
            f"数据集 Writer SDK 不可用：\n{result.stdout}\n{result.stderr}\n{guidance}"
        )
