#!/usr/bin/env bash
set -euo pipefail

# Compatibility entry: the workbench owns hardware profiles and interpreter setup.
workbench_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec "$workbench_root/scripts/run_teleop.sh" "$@"
