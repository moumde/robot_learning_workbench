#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. Install uv, then rerun this script." >&2
  exit 1
fi

echo "==> Installing OpenPI and camera/LinkerHand test dependencies"
"$ROOT/scripts/bootstrap.sh"

echo
echo "==> Installing NRC, camera and HMI dependencies"
"$ROOT/scripts/setup_nrc_env.sh"

echo
echo "All project Python environments are installed and checked."
