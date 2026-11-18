#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
root="${MODEL_STORAGE:-$HOME/phd-models}"
mkdir -p "$root"/{venv,cache/uv,python,tmp,results,logs}
export UV_PROJECT_ENVIRONMENT="$root/venv/claim-extractor"
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/python"
export UV_LINK_MODE=hardlink TMPDIR="$root/tmp"
mode="${1:-run}"
if (( $# )); then shift; fi
case "$mode" in
  prepare)
    uv run --frozen --python 3.10 scripts/prepare-models.py --storage "$root" "$@"
    ;;
  run|check)
    export UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never
    args=()
    [[ "$mode" == check ]] && args+=(--check)
    uv run --frozen --no-sync --python 3.10 scripts/run_models.py \
      --storage "$root" --offline --model-timeout "${MODEL_TIMEOUT_SECONDS:-7200}" \
      "${args[@]}" "$@"
    ;;
  *) echo 'Usage: bash run-cuba.sh [prepare|run|check] [options]' >&2; exit 2 ;;
esac
