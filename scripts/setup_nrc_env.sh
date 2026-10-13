#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_ROOT="$ROOT/module/openpi"
NRC_ROOT="$ROOT/module/nrc"
NRC_ENV="$NRC_ROOT/.venv"
NRC_PYTHON_VERSION="${NRC_PYTHON_VERSION:-3.12}"

if [[ ! -f "$OPENPI_ROOT/packages/openpi-client/pyproject.toml" ]]; then
  echo "ERROR: OpenPI client package is missing: $OPENPI_ROOT/packages/openpi-client" >&2
  echo "确认 module/openpi 源码目录完整后再重试。" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. Install it before creating the NRC environment." >&2
  exit 1
fi

mkdir -p "$NRC_ROOT"
printf 'Creating/updating NRC environment: %s (Python %s)\n' "$NRC_ENV" "$NRC_PYTHON_VERSION"
uv venv --python "$NRC_PYTHON_VERSION" "$NRC_ENV"

# The client does not need the full OpenPI training stack.  Keep this
# environment independent from module/openpi/.venv while installing the
# network client, LinkerHand dependencies, and parquet reader for trajectory replay.
uv pip install \
  --python "$NRC_ENV/bin/python" \
  -e "$OPENPI_ROOT/packages/openpi-client" \
  pymodbus==3.5.1 \
  pyserial \
  PyYAML \
  pandas \
  pyarrow \
  PySide6

echo
echo "NRC environment is ready: $NRC_ENV"
echo "Run a program with: ./scripts/run_nrc.sh python <program> [args...]"
