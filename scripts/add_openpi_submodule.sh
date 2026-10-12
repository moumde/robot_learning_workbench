#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENPI_PATH="$ROOT/module/openpi"
OPENPI_URL="https://github.com/Physical-Intelligence/openpi.git"

if ! git -C "$ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: 当前工作台还不是 Git 仓库。请先在项目根目录运行 git init 并提交基线。" >&2
  exit 1
fi

if [[ -f "$ROOT/.gitmodules" ]] && git -C "$ROOT" config -f "$ROOT/.gitmodules" --get-regexp '^submodule\..*\.path$' 2>/dev/null | awk '$2 == "module/openpi" { found=1 } END { exit !found }'; then
  echo "OpenPI 已登记为 Submodule，正在初始化："
  git -C "$ROOT" submodule update --init --recursive module/openpi
else
  if [[ -e "$OPENPI_PATH" ]]; then
    if [[ -n "$(find "$OPENPI_PATH" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
      echo "ERROR: $OPENPI_PATH 已存在且非空。为避免覆盖本地内容，已停止。" >&2
      echo "请备份/移动该目录后再次执行。" >&2
      exit 1
    fi
    rmdir "$OPENPI_PATH"
  fi
  mkdir -p "$ROOT/module"
  git -C "$ROOT" submodule add "$OPENPI_URL" module/openpi
  git -C "$OPENPI_PATH" submodule update --init --recursive
fi

echo
echo "OpenPI checkout: $OPENPI_PATH"
echo "OpenPI commit:   $(git -C "$OPENPI_PATH" rev-parse HEAD)"
echo
echo "下一步由维护者审查并提交：git add .gitmodules module/openpi"
