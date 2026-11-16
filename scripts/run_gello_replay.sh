#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/teleop_python.sh"
select_teleop_python "$ROOT"
EXECUTE=false
READ_ONLY=false
for argument in "$@"; do
  if [[ "$argument" == --execute ]]; then EXECUTE=true; fi
  if [[ "$argument" == --help || "$argument" == -h ]]; then READ_ONLY=true; fi
done
if [[ "$EXECUTE" == true && "$READ_ONLY" == false ]]; then
  prepare_teleop_python_if_missing "$ROOT"
fi

# The replay CLI previews by default; device access requires --execute.
export NRC_PYTHON="$TELEOP_PYTHON"
exec "$ROOT/scripts/run_nrc.sh" "$TELEOP_PYTHON" -m teleop.gello_cr.cli.replay "$@"
