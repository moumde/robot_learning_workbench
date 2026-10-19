#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NRC_PYTHON="$ROOT/module/nrc/.venv/bin/python"

if [[ ! -x "$NRC_PYTHON" ]]; then
  echo "ERROR: NRC/HMI environment is missing: $NRC_PYTHON" >&2
  echo "Run ./scripts/setup_nrc_env.sh first." >&2
  exit 1
fi

# Do not inherit Conda/system Qt plugin paths into the PySide6 GUI process.
unset QT_PLUGIN_PATH || true
unset QT_QPA_PLATFORM_PLUGIN_PATH || true
unset QML2_IMPORT_PATH || true
unset QML_IMPORT_PATH || true
unset LD_PRELOAD || true

PYSIDE_DIR="$($NRC_PYTHON -c 'import PySide6, os; print(os.path.dirname(PySide6.__file__))')"
QT_LIB="$PYSIDE_DIR/Qt/lib"

if [[ ! -f "$QT_LIB/libQt6Core.so.6" ]]; then
  echo "ERROR: PySide6 Qt libraries not found: $QT_LIB" >&2
  exit 1
fi

# PySide6 must use the Qt libraries shipped by the same wheel. System libraries
# remain available through the dynamic linker's normal default search paths.
export LD_LIBRARY_PATH="$QT_LIB"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec "$NRC_PYTHON" "$ROOT/hmi/trainui/app.py" "$@"
