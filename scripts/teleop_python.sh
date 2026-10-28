#!/usr/bin/env bash
# Shared interpreter policy for teleop launch, replay, and environment setup.

select_teleop_python() {
  local root="$1"
  TELEOP_PYTHON_SOURCE=explicit
  if [[ -n "${GELLO_CR_PYTHON:-}" ]]; then
    TELEOP_PYTHON="$GELLO_CR_PYTHON"
  elif [[ -n "${NRC_PYTHON:-}" ]]; then
    TELEOP_PYTHON="$NRC_PYTHON"
  elif [[ -n "${NRC_ENV:-}" ]]; then
    TELEOP_PYTHON="$NRC_ENV/bin/python"
  else
    TELEOP_PYTHON="$root/module/nrc/.venv/bin/python"
    TELEOP_PYTHON_SOURCE=default
    if [[ -n "${CONDA_PREFIX:-}" ]]; then
      local candidate="$CONDA_PREFIX/bin/python"
      local reason
      if [[ -x "$candidate" ]] && reason="$("$candidate" -c '
import sys
assert sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12), "NRC requires CPython 3.12"
import numpy
version = tuple(map(int, numpy.__version__.split(".")[:2]))
assert (1, 26) <= version < (2, 0), "NRC requires NumPy >=1.26,<2"
import cv2, serial, pyarrow
from PySide6.QtWidgets import QApplication
import pymodbus
assert pymodbus.__version__ == "3.5.1", "O6 requires pymodbus==3.5.1"
from pymodbus.client import ModbusSerialClient
import pyrealsense2
' 2>&1)"; then
        TELEOP_PYTHON="$candidate"
        TELEOP_PYTHON_SOURCE=conda
      else
        printf 'Active Conda cannot run GELLO/NRC; using the project environment: %s\n%s\n' \
          "$TELEOP_PYTHON" "${reason:-Python executable is missing: $candidate}" >&2
      fi
    fi
  fi
}

prepare_teleop_python_if_missing() {
  local root="$1"
  if [[ "$TELEOP_PYTHON_SOURCE" == default && ! -x "$TELEOP_PYTHON" ]]; then
    echo "Preparing the independent teleop environment: $TELEOP_PYTHON" >&2
    "$root/scripts/setup_teleop_env.sh"
  fi
}
