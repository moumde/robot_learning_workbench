#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: scripts/setup_teleop_env.sh

Reuse the parent's NRC Python 3.12 environment and install GELLO UI, serial,
RealSense and HDF5 dependencies. Create the default NRC environment if missing.
Select an existing interpreter with GELLO_CR_PYTHON or NRC_PYTHON (in that order).
This script does not connect devices or install LeRobot/training dependencies.

Install the independent default V2.1 writer separately:
  scripts/setup_gello_writer_env.sh v21
EOF
  exit 0
fi
if [[ "$#" -ne 0 ]]; then
  echo "ERROR: Unknown arguments. Use --help." >&2
  exit 2
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. Install it before creating the teleop environment." >&2
  exit 1
fi

DEFAULT_PYTHON="$ROOT/module/nrc/.venv/bin/python"
TELEOP_PYTHON="${GELLO_CR_PYTHON:-${NRC_PYTHON:-${NRC_ENV:-$ROOT/module/nrc/.venv}/bin/python}}"
if [[ ! -x "$TELEOP_PYTHON" ]]; then
  if [[ "$TELEOP_PYTHON" != "$DEFAULT_PYTHON" ]]; then
    echo "ERROR: Selected Python environment is missing: $TELEOP_PYTHON" >&2
    exit 1
  fi
  "$ROOT/scripts/setup_nrc_env.sh"
fi
TELEOP_PYTHON_VERSION="$("$TELEOP_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$TELEOP_PYTHON_VERSION" != "3.12" ]]; then
  echo "ERROR: GELLO/NRC requires Python 3.12, found $TELEOP_PYTHON_VERSION ($TELEOP_PYTHON)" >&2
  exit 1
fi

# Use the local GELLO source and only its declared runtime/UI/HDF5 extras.
# In particular, never install vendor/gello/requirements.txt into this environment.
# Resolve the parent client in the same transaction so its NumPy <2 ABI is kept.
uv pip install --python "$TELEOP_PYTHON" \
  -e "$ROOT/module/openpi/packages/openpi-client" \
  -e "$ROOT[ui,hdf5,data-validation]" \
  'numpy>=1.26,<2' \
  'opencv-python>=4.8,<4.12' \
  'pyarrow>=21,<22' \
  dynamixel-sdk \
  pyrealsense2 \
  pymodbus==3.5.1

printf '\nTeleop environment is ready: %s\n' "$TELEOP_PYTHON"
echo "Check configuration without devices: ./scripts/run_teleop.sh --check-only"
echo "Install the default V2.1 writer: ./scripts/setup_gello_writer_env.sh v21"
