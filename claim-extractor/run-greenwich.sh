#!/usr/bin/env bash
set -uo pipefail
root="${MODEL_STORAGE:-$HOME/greenwich-models}"
expected='marcele_araponga@150.164.2.42:/home/marcele_araponga/phd-models'
read -r type target source < <(findmnt -n -o FSTYPE,TARGET,SOURCE --mountpoint "$root")
if [[ "${type:-}" != fuse.sshfs || "${source:-}" != "$expected" ]]; then
  echo "Greenwich SSHFS is not mounted at $root" >&2
  exit 1
fi
cd "$(dirname "$0")" || exit 1
mkdir -p "$root"/{venv,cache/uv,tmp,results,logs}
export UV_PROJECT_ENVIRONMENT="$root/venv/claim-extractor"
export UV_CACHE_DIR="$root/cache/uv" TMPDIR="$root/tmp"
export UV_LINK_MODE=copy
timeout_seconds="${MODEL_TIMEOUT_SECONDS:-7200}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
failed=0
for model in gemma-2b-aps gemma-7b-aps detective-qwen3b newsscope babelscape-t5 claimpt principled-2b principled-4b fc-claim-det-t5 sagesse-mistral dongyru-mistral mistral-instruct-v02; do
  read -r type target source < <(findmnt -n -o FSTYPE,TARGET,SOURCE --mountpoint "$root")
  if [[ "${type:-}" != fuse.sshfs || "${source:-}" != "$expected" ]]; then
    echo "Greenwich SSHFS disconnected; stopping" >&2
    exit 1
  fi
  args=()
  [[ "$model" == babelscape-t5 ]] && args+=(--context-tokens 512)
  if [[ "$model" == dongyru-mistral || "$model" == mistral-instruct-v02 ]]; then
    args+=(--prompt-file "$model=$PWD/prompts/shared-zero-shot-v2.md")
  fi
  echo "Running $model"
  uv run --frozen run_models.py --offline --remote-storage "$root" --models "$model" \
    --model-timeout "$timeout_seconds" --output-dir "$root/results/$run_id" \
    "${args[@]}" 2>&1 | tee "$root/logs/$run_id-$model.log"
  status=${PIPESTATUS[0]}
  if (( status != 0 )); then echo "$model: failed ($status)"; failed=1; fi
done
exit "$failed"
