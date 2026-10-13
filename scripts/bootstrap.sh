#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 未找到 uv。先按 README 安装 uv，再运行本脚本。" >&2
  exit 1
fi
if [[ ! -f "$ROOT/module/openpi/pyproject.toml" ]]; then
  echo "ERROR: 缺少 module/openpi 源码目录。请确认仓库内容完整。" >&2
  exit 1
fi

"$ROOT/scripts/setup_openpi_env.sh"
"$ROOT/scripts/verify_openpi_env.sh"
