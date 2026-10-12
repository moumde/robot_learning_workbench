#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_ROOT="$ROOT/module/openpi"
PYTHON="$OPENPI_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: OpenPI venv not found: $PYTHON" >&2
  echo "Run ./scripts/setup_openpi_env.sh first." >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import importlib
import os
import sys

print(f"Python executable: {sys.executable}")
print(f"Python version:   {sys.version.split()[0]}")

modules = ("openpi", "lerobot", "jax", "torch", "cv2")
failed = []
for name in modules:
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "(version n/a)")
        location = getattr(mod, "__file__", "(namespace package)")
        print(f"[OK] {name}: version={version}; path={location}")
    except Exception as exc:
        failed.append(name)
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")

try:
    import torch
    torch_cuda = torch.cuda.is_available()
    print(f"Torch CUDA available: {torch_cuda}")
    if torch_cuda:
        print(f"Torch CUDA device:    {torch.cuda.get_device_name(0)}")
except Exception as exc:
    torch_cuda = False
    print(f"Torch CUDA check failed: {type(exc).__name__}: {exc}")

try:
    import jax
    devices = jax.devices()
    print(f"JAX devices:          {devices}")
    jax_gpu = any(getattr(d, "platform", "") in ("gpu", "cuda") for d in devices)
except Exception as exc:
    jax_gpu = False
    print(f"JAX device check failed: {type(exc).__name__}: {exc}")

if failed:
    print(f"\nFAILED imports: {', '.join(failed)}", file=sys.stderr)
    sys.exit(1)

if not (torch_cuda or jax_gpu):
    print("\nWARN: Packages imported, but neither Torch nor JAX reports a GPU.")
    print("This may be expected on a CPU-only developer machine; GPU training/inference is not validated.")
    if os.environ.get("STRICT_GPU", "0") == "1":
        sys.exit(2)

print("\nOpenPI environment smoke test passed.")
PY

if command -v nvidia-smi >/dev/null 2>&1; then
  echo
echo "--- nvidia-smi ---"
  nvidia-smi
else
  echo "WARN: nvidia-smi not found; NVIDIA driver/GPU availability not checked by the host." >&2
fi
