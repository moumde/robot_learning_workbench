#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TELEOP_PYTHON="${GELLO_CR_PYTHON:-${NRC_PYTHON:-${NRC_ENV:-$ROOT/module/nrc/.venv}/bin/python}}"

# Keep the NRC ABI and libpython handling in the parent's common launcher.
export NRC_PYTHON="$TELEOP_PYTHON"
exec "$ROOT/scripts/run_nrc.sh" "$TELEOP_PYTHON" -m hmi.collection "$@"
