#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_ROOT="$ROOT/module/openpi"

if [[ ! -f "$OPENPI_ROOT/pyproject.toml" ]]; then
  echo "ERROR: module/openpi 源码目录缺失。请确认仓库内容完整。" >&2
  exit 1
fi
if [[ ! -x "$OPENPI_ROOT/.venv/bin/python" ]]; then
  echo "ERROR: OpenPI environment is missing. Run ./scripts/setup_openpi_env.sh first." >&2
  exit 1
fi
if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 <command> [args...]" >&2
  echo "Example: $0 scripts/train.py <config_name> --exp-name=<experiment_name>" >&2
  exit 2
fi

export UV_PROJECT_ENVIRONMENT="$OPENPI_ROOT/.venv"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export HF_LEROBOT_HOME="${HF_LEROBOT_HOME:-$ROOT/dataset/train}"
cd "$OPENPI_ROOT"
exec uv run --project "$OPENPI_ROOT" "$@"
