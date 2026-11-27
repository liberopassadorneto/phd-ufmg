#!/usr/bin/env bash
set -euo pipefail

repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${DRIVE_OUTPUT_DESTINATION:-phd-drive:phd-ufmg}"
storage="${MODEL_STORAGE:-$HOME/phd-models}"

flags=()
if [[ "${1:-}" == --dry-run ]]; then
  flags+=(--dry-run)
  shift
fi

if (( $# == 0 )); then
  if [[ -d "$repo/libero/claim-extractor/results" ]]; then
    rclone copy "${flags[@]}" "$repo/libero/claim-extractor/results" "$destination/claim-extractor/results"
  fi
  if [[ -d "$storage/results" ]]; then
    rclone copy "${flags[@]}" "$storage/results" "$destination/claim-extractor/cuba-results"
  fi
  exit
fi

if (( $# != 2 )) || [[ ! -e "$1" || -z "$2" || "$2" == /* || "/$2/" == */../* ]]; then
  echo "Usage: bash backup-outputs.sh [--dry-run] [SOURCE DRIVE_SUBFOLDER]" >&2
  exit 2
fi

rclone copy "${flags[@]}" -- "$1" "$destination/$2"
