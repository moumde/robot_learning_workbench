#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${repo_root}/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${GELLO_CR_DATA_PYTHON:-python3.12}" -m gello_cr.recording.validate_dataset "$@"
