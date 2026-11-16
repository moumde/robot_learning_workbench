#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: scripts/setup_gello_writer_env.sh <v21|v3>

Create/update an independent Python 3.12 dataset writer environment:
  v21: module/gello_writers/v21/.venv, official lerobot==0.3.3 (default format)
  v3:  module/gello_writers/v3/.venv, explicit GELLO_V3_LEROBOT_SPEC required

V3 must provide RGBEncoderConfig and LeRobotDataset.create streaming_encoding.
Set GELLO_V3_LEROBOT_SPEC to a verified local source tree or immutable Git spec.
Example: GELLO_V3_LEROBOT_SPEC=/opt/verified/lerobot scripts/setup_gello_writer_env.sh v3

Only dataset dependencies and CPU PyTorch wheels are installed. No device is
opened. HDF5 uses the NRC environment from setup_teleop_env.sh.
EOF
  exit 0
fi
if [[ "$#" -ne 1 || ( "$1" != "v21" && "$1" != "v3" ) ]]; then
  echo "ERROR: Choose v21 or v3. Use --help for details." >&2
  exit 2
fi
WRITER_FORMAT="$1"
if [[ "$WRITER_FORMAT" == "v3" && -z "${GELLO_V3_LEROBOT_SPEC:-}" ]]; then
  echo "ERROR: V3 requires GELLO_V3_LEROBOT_SPEC pointing to verified source with the encoder API." >&2
  exit 2
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required." >&2
  exit 1
fi
WRITER_ENV="$ROOT/module/gello_writers/$WRITER_FORMAT/.venv"
WRITER_PYTHON="$WRITER_ENV/bin/python"
if [[ ! -x "$WRITER_PYTHON" ]]; then
  uv venv --python 3.12 "$WRITER_ENV"
fi
WRITER_PYTHON_VERSION="$("$WRITER_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$WRITER_PYTHON_VERSION" != "3.12" ]]; then
  echo "ERROR: Writer environment requires Python 3.12, found $WRITER_PYTHON_VERSION." >&2
  exit 1
fi

# The dataset SDK imports torch/torchvision even for CPU-only encoding.
uv pip install --python "$WRITER_PYTHON" \
  --index-url https://download.pytorch.org/whl/cpu \
  'torch==2.7.1' 'torchvision==0.22.1'
uv pip install --python "$WRITER_PYTHON" \
  'numpy>=2,<3' 'pandas>=2,<3' 'pyarrow>=21,<30' 'av>=15,<16' \
  'Pillow>=10,<13' 'einops>=0.8,<0.9' 'jsonlines>=4,<5' \
  'setuptools>=71,<82' packaging tqdm
if [[ "$WRITER_FORMAT" == "v21" ]]; then
  uv pip install --python "$WRITER_PYTHON" \
    'datasets==3.6.0' 'huggingface-hub>=0.34.2,<1' 'draccus==0.10.0'
  LEROBOT_SPEC='lerobot==0.3.3'
else
  uv pip install --python "$WRITER_PYTHON" \
    'datasets>=4.8,<5' 'huggingface-hub>=1.6,<2' 'draccus>=0.11.6,<0.12' \
    'gymnasium>=1.1,<2' safetensors termcolor
  LEROBOT_SPEC="$GELLO_V3_LEROBOT_SPEC"
fi
# Install only the dataset adapter's dependencies above, excluding the SDK's
# policy/training, visualization and hardware extras from the writer process.
uv pip install --python "$WRITER_PYTHON" --no-deps "$LEROBOT_SPEC"
"$WRITER_PYTHON" - "$WRITER_FORMAT" <<'PY'
import inspect
import sys

from lerobot.datasets.lerobot_dataset import CODEBASE_VERSION, LeRobotDataset

if sys.argv[1] == "v21":
    if CODEBASE_VERSION != "v2.1":
        raise SystemExit("Expected official LeRobot V2.1 (lerobot==0.3.3)")
else:
    from lerobot.configs.video import RGBEncoderConfig

    required = {"rgb_encoder", "streaming_encoding", "encoder_queue_maxsize", "encoder_threads"}
    if not CODEBASE_VERSION.startswith("v3.") or not required <= set(inspect.signature(LeRobotDataset.create).parameters):
        raise SystemExit("V3 source lacks the required streaming encoder API")
    RGBEncoderConfig(vcodec="h264", pix_fmt="yuv420p", crf=18, preset="fast", g=20)
print(f"Writer SDK API is available: {CODEBASE_VERSION}; {sys.executable}")
PY

printf '\nWriter environment: %s\n' "$WRITER_PYTHON"
echo "Run dataset write/merge/recovery tests before using this environment for collection."
