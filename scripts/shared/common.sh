#!/usr/bin/env bash
# Shared environment bootstrap. Source this file; do not execute it.

apy_project_root() {
  (cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
}

PROJECT_ROOT="${PROJECT_ROOT:-$(apy_project_root)}"

apy_path_device() {
  local path="$1"
  local parent
  while [ -n "$path" ] && [ ! -e "$path" ]; do
    parent="$(dirname "$path")"
    [ "$parent" = "$path" ] && break
    path="$parent"
  done
  [ -e "$path" ] || return 1
  stat -c '%d' "$path" 2>/dev/null || stat -f '%d' "$path" 2>/dev/null
}

apy_export_uv_link_mode() {
  local mode="${UV_LINK_MODE:-}"
  if [ -n "$mode" ] && [ "${mode,,}" != "auto" ]; then
    export UV_LINK_MODE
    return 0
  fi

  unset UV_LINK_MODE
  command -v uv >/dev/null 2>&1 || return 0
  local cache_device
  local root_device
  cache_device="$(apy_path_device "$(uv cache dir 2>/dev/null)")" || cache_device=""
  root_device="$(apy_path_device "$PROJECT_ROOT/.venv")" || root_device=""
  if [ -n "$cache_device" ] && [ -n "$root_device" ] && [ "$cache_device" != "$root_device" ]; then
    export UV_LINK_MODE=copy
  fi
}

apy_export_tool_caches() {
  export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-$DATA_DIR/cache/ruff}"
  export MYPY_CACHE_DIR="${MYPY_CACHE_DIR:-$DATA_DIR/cache/mypy}"
}

apy_load_env() {
  # shellcheck source=/dev/null
  if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    . "$PROJECT_ROOT/.env"
    set +a
  fi
  DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/.data}"
  case "$DATA_DIR" in
    /*) ;;
    *) DATA_DIR="$PROJECT_ROOT/$DATA_DIR" ;;
  esac
  export DATA_DIR
  apy_export_tool_caches
  apy_export_uv_link_mode
}
