#!/usr/bin/env bash
set -euo pipefail

if [[ ! -r /etc/os-release ]]; then
  echo "ERROR: 无法识别 Linux 发行版。此脚本只支持 Ubuntu/Debian 系 apt 环境。" >&2
  exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  echo "ERROR: 当前系统为 ${PRETTY_NAME:-unknown}；此脚本只面向 Ubuntu/Debian。" >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1 && [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: 请安装 sudo 或以 root 身份运行。" >&2
  exit 1
fi

SUDO=()
if [[ "${EUID}" -ne 0 ]]; then SUDO=(sudo); fi

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y \
  ca-certificates \
  curl \
  git \
  git-lfs \
  build-essential \
  cmake \
  pkg-config \
  libgl1 \
  libglib2.0-0 \
  ffmpeg

git lfs install

echo
echo "System tools installed. NVIDIA driver was not installed or modified."
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "WARN: 未发现 nvidia-smi。CPU 环境可用于部分开发/导入测试，但 GPU 推理和训练需要合适的 NVIDIA 驱动/GPU。"
fi
