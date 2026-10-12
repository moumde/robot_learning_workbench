#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_ROOT="$ROOT/module/openpi"

if [[ ! -d "$OPENPI_ROOT" || ! -f "$OPENPI_ROOT/pyproject.toml" ]]; then
  echo "ERROR: 未找到 module/openpi。请先由维护者执行 scripts/add_openpi_submodule.sh，" >&2
  echo "并确保你已使用 git clone --recurse-submodules 获取仓库。" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 未找到 uv。请先安装：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo '然后执行：export PATH="$HOME/.local/bin:$PATH"' >&2
  exit 1
fi

if [[ ! -f "$OPENPI_ROOT/uv.lock" || ! -f "$OPENPI_ROOT/.python-version" ]]; then
  echo "ERROR: OpenPI 的 uv.lock 或 .python-version 不存在；请检查 Submodule 版本。" >&2
  exit 1
fi

# Ensure OpenPI's nested submodules are present before resolving dependencies.
git -C "$OPENPI_ROOT" submodule update --init --recursive

# Force all uv operations to use the environment inside the pinned OpenPI checkout,
# even if the caller happens to have another venv/Conda environment activated.
export UV_PROJECT_ENVIRONMENT="$OPENPI_ROOT/.venv"
export GIT_LFS_SKIP_SMUDGE=1

printf 'OpenPI path: %s\n' "$OPENPI_ROOT"
printf 'uv version:  %s\n' "$(uv --version)"
printf 'Environment: %s\n\n' "$UV_PROJECT_ENVIRONMENT"

# --locked prevents changing the checked-in upstream lockfile during installation.
(cd "$OPENPI_ROOT" && uv sync --locked)

# Keep the editable install explicitly targeted at OpenPI's own interpreter.
uv pip install --python "$OPENPI_ROOT/.venv/bin/python" -e "$OPENPI_ROOT"

echo
echo "Environment installation complete: $OPENPI_ROOT/.venv"
echo "Next: ./scripts/verify_openpi_env.sh"
