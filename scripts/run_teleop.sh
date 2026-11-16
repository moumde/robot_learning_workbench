#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/teleop_python.sh"
select_teleop_python "$ROOT"
READ_ONLY=false
for argument in "$@"; do
  if [[ "$argument" == --help || "$argument" == -h || "$argument" == --check-only ]]; then
    READ_ONLY=true
  fi
done
if [[ "$READ_ONLY" == false ]]; then
  prepare_teleop_python_if_missing "$ROOT"
fi

# Keep the NRC ABI and libpython handling in the parent's common launcher.
export NRC_PYTHON="$TELEOP_PYTHON"
exec "$ROOT/scripts/run_nrc.sh" "$TELEOP_PYTHON" -m teleop.gello_cr.ui "$@"
