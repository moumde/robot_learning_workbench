#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NRC_ROOT="$ROOT/module/nrc"
NRC_ENV="${NRC_ENV:-$NRC_ROOT/.venv}"
NRC_PYTHON="${NRC_PYTHON:-$NRC_ENV/bin/python}"

if [[ ! -x "$NRC_PYTHON" ]]; then
  echo "ERROR: NRC Python environment is missing: $NRC_PYTHON" >&2
  echo "Run ./scripts/setup_nrc_env.sh first." >&2
  exit 1
fi
if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 <command> [args...]" >&2
  echo "Example: $0 python test/test_nrc_interface.py --ip 192.168.2.14" >&2
  exit 2
fi

NRC_PYTHON_VERSION="$("$NRC_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$NRC_PYTHON_VERSION" != "3.12" ]]; then
  echo "ERROR: NRC environment must use Python 3.12, found $NRC_PYTHON_VERSION ($NRC_PYTHON)" >&2
  exit 1
fi
NRC_BIN_DIR="$(cd "$(dirname "$NRC_PYTHON")" && pwd)"

# The vendor extension is linked against libpython3.12.  uv-managed Python
# installations keep that library beside the interpreter rather than in the
# system dynamic-linker cache, so expose its directory explicitly.
NRC_PYTHON_LIBDIR="$("$NRC_PYTHON" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')"
if [[ -n "$NRC_PYTHON_LIBDIR" && -d "$NRC_PYTHON_LIBDIR" ]]; then
  export LD_LIBRARY_PATH="$NRC_PYTHON_LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
# Keep environment metadata consistent with the executable we actually selected.
# Conda has no pyvenv.cfg and must not inherit an unrelated virtualenv marker.
NRC_SELECTED_PREFIX="$(cd "$NRC_BIN_DIR/.." && pwd)"
if [[ -f "$NRC_SELECTED_PREFIX/pyvenv.cfg" ]]; then
  export VIRTUAL_ENV="$NRC_SELECTED_PREFIX"
else
  unset VIRTUAL_ENV
fi
export PATH="$NRC_BIN_DIR:$PATH"
cd "$ROOT"
exec "$@"
