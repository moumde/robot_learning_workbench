#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_ROOT="$ROOT/module/openpi"
NRC_ROOT="$ROOT/module/nrc"
NRC_ENV="$NRC_ROOT/.venv"
NRC_PYTHON_VERSION="${NRC_PYTHON_VERSION:-3.12}"

if [[ "$NRC_PYTHON_VERSION" != "3.12" ]]; then
  echo "ERROR: The vendored NRC native SDK requires CPython 3.12; got $NRC_PYTHON_VERSION." >&2
  exit 1
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: The vendored NRC native SDK currently supports Linux x86_64 only." >&2
  exit 1
fi

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
if [[ -x "$NRC_ENV/bin/python" ]]; then
  EXISTING_NRC_VERSION="$("$NRC_ENV/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$EXISTING_NRC_VERSION" != "$NRC_PYTHON_VERSION" ]]; then
    echo "ERROR: Existing NRC environment uses Python $EXISTING_NRC_VERSION; expected $NRC_PYTHON_VERSION." >&2
    echo "Move the environment aside or remove it explicitly, then rerun this script." >&2
    exit 1
  fi
else
  uv venv --python "$NRC_PYTHON_VERSION" "$NRC_ENV"
fi

# Keep this environment independent from module/openpi/.venv. Install the
# deployment camera backend, HMI, parquet replay, and hand transport packages.
uv pip install \
  --python "$NRC_ENV/bin/python" \
  -e "$OPENPI_ROOT/packages/openpi-client" \
  "lerobot[intelrealsense] @ git+https://github.com/huggingface/lerobot@0cf864870cf29f4738d3ade893e6fd13fbd7cdb5" \
  "numpy>=1.26,<2" \
  "opencv-python-headless>=4.10,<5" \
  pymodbus==3.5.1 \
  pyserial \
  python-can \
  pandas \
  pyarrow \
  PyYAML \
  "PySide6>=6.7,<7"

uv pip check --python "$NRC_ENV/bin/python"

"$NRC_ENV/bin/python" - <<'PY'
import importlib
import sys

modules = (
    "openpi_client",
    "lerobot",
    "numpy",
    "cv2",
    "pyrealsense2",
    "pymodbus",
    "serial",
    "yaml",
    "pandas",
    "pyarrow",
    "PySide6",
)
failed = []
print(f"Python: {sys.version.split()[0]} ({sys.executable})")
for name in modules:
    try:
        importlib.import_module(name)
        print(f"[OK] {name}")
    except Exception as exc:
        failed.append(name)
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
if failed:
    raise SystemExit(f"NRC/HMI dependency imports failed: {', '.join(failed)}")
PY

NRC_PYTHON_LIBDIR="$("$NRC_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')"
PYTHONPATH="$ROOT:$ROOT/vendor/actuator/linkerhand-python-sdk" \
LD_LIBRARY_PATH="$NRC_PYTHON_LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  "$NRC_ENV/bin/python" - <<'PY'
from LinkerHand.linker_hand_api import LinkerHandApi  # noqa: F401
from vendor.camera.d435.camera_interface import _load_lerobot_backend
from vendor.nrc_interface.nrc_linux_x86_64 import nrc_interface  # noqa: F401

print(f"[OK] NRC native SDK and LinkerHand SDK; RealSense backend={_load_lerobot_backend()[0]}")
PY

echo
echo "NRC/HMI environment is ready: $NRC_ENV"
echo "Run a program with: ./scripts/run_nrc.sh python <program> [args...]"
