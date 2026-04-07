#!/usr/bin/env bash

set -euo pipefail

DRY_RUN=false
KEEP_JOURNAL_DAYS="${KEEP_JOURNAL_DAYS:-7}"
TMP_CLEAN_DAYS="${TMP_CLEAN_DAYS:-3}"

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

log() {
  printf '[host-cleanup] %s\n' "$1"
}

run_cmd() {
  local cmd="$1"
  if $DRY_RUN; then
    printf '[host-cleanup][dry-run] %s\n' "${cmd}"
  else
    bash -lc "${cmd}"
  fi
}

bytes_available() {
  df -B1 / | awk 'NR==2 {print $4}'
}

before_bytes="$(bytes_available)"
log "disk before: $(df -h / | awk 'NR==2 {print $4 " free / " $2 " total (" $5 " used)"}')"

# Docker cache/image cleanup (safe: no running container data removed).
run_cmd "docker builder prune -af"
run_cmd "docker image prune -f"
run_cmd "docker container prune -f"
run_cmd "docker network prune -f"

# Keep recent logs, clean historical journal/log temp artifacts.
if command -v journalctl >/dev/null 2>&1; then
  run_cmd "journalctl --vacuum-time=${KEEP_JOURNAL_DAYS}d"
fi

# Remove stale temp files only.
run_cmd "find /tmp -xdev -mindepth 1 -mtime +${TMP_CLEAN_DAYS} -print -delete"
run_cmd "find /var/tmp -xdev -mindepth 1 -mtime +${TMP_CLEAN_DAYS} -print -delete"

# Package cache cleanup.
if command -v apt-get >/dev/null 2>&1; then
  run_cmd "apt-get clean"
fi

after_bytes="$(bytes_available)"
reclaimed_bytes=$((after_bytes - before_bytes))
if (( reclaimed_bytes < 0 )); then
  reclaimed_bytes=0
fi

log "disk after: $(df -h / | awk 'NR==2 {print $4 " free / " $2 " total (" $5 " used)"}')"
log "reclaimed bytes: ${reclaimed_bytes}"
