#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

WEB_LOCAL_BASE="${WEB_LOCAL_BASE:-http://127.0.0.1:3210}"
WEB_PUBLIC_BASE="${WEB_PUBLIC_BASE:-https://datacenter.oran.cn}"
API_LOCAL_BASE="${API_LOCAL_BASE:-http://127.0.0.1:8000}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-90}"
SKIP_BUILD="${SKIP_BUILD:-0}"
WATCHDOG_LOG_FILE="${WATCHDOG_LOG_FILE:-/tmp/xhs_search_watchdog.log}"

log() {
  printf '[deploy-web] %s\n' "$1"
}

probe() {
  local url="$1"
  local label="$2"
  if curl -fsS --max-time 8 "$url" >/dev/null; then
    log "PASS ${label} -> ${url}"
    return 0
  fi
  log "FAIL ${label} -> ${url}"
  return 1
}

probe_static_assets() {
  local base="$1"
  local path="$2"
  local label="$3"
  if WEB_BASE="${base}" WEB_PAGE_PATH="${path}" TIMEOUT=15 "${ROOT_DIR}/scripts/check_web_static_assets.sh" >/dev/null; then
    log "PASS ${label} -> ${base}${path}"
    return 0
  fi
  log "FAIL ${label} -> ${base}${path}"
  return 1
}

smoke_check() {
  local status=0
  probe "${WEB_LOCAL_BASE}/zh/datacenter" "web local datacenter" || status=1
  probe "${WEB_PUBLIC_BASE}/zh/datacenter/xhs" "web public xhs home" || status=1
  probe "${WEB_PUBLIC_BASE}/zh/datacenter/xhs/search?type=category&q=YSL" "web public xhs search" || status=1
  probe_static_assets "${WEB_LOCAL_BASE}" "/zh/datacenter/xhs" "web local static assets" || status=1
  probe_static_assets "${WEB_PUBLIC_BASE}" "/zh/datacenter/xhs" "web public static assets" || status=1
  probe "${API_LOCAL_BASE}/health" "api health" || status=1
  probe "${API_LOCAL_BASE}/api/v1/dashboard/xhs/overview?days=90" "api dashboard overview" || status=1
  probe_search_ready || status=1
  return "${status}"
}

probe_search_ready() {
  local payload
  payload="$(curl -fsS --max-time 12 -X POST "${WEB_LOCAL_BASE}/api/search/brand-category" \
    -H "Content-Type: application/json" \
    --data '{"locale":"zh","query":"YSL","sort":"stat","order":"desc","page":1,"size":30,"min_like":1,"date_range":30,"freshness_hours":24,"force_refresh":false}' || true)"
  if [[ -z "${payload}" ]]; then
    log "FAIL search api gate (empty response)"
    return 1
  fi
  if grep -q '"errorType":"upstream_misconfigured"' <<<"${payload}"; then
    log "FAIL search api gate (upstream_misconfigured)"
    return 1
  fi
  if grep -q '"status":"ready"' <<<"${payload}" && grep -q '"noteId":"' <<<"${payload}"; then
    log "PASS search api gate (YSL ready with items)"
    return 0
  fi
  log "FAIL search api gate (not ready with items)"
  return 1
}

wait_until_ready() {
  local waited=0
  while [[ "${waited}" -lt "${MAX_WAIT_SECONDS}" ]]; do
    if smoke_check; then
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

rollback() {
  if ! docker image inspect xhs_web:rollback >/dev/null 2>&1; then
    log "No rollback image found (xhs_web:rollback)."
    return 1
  fi
  log "Rollback: restoring xhs_web:rollback -> xhs_web:current"
  docker image tag xhs_web:rollback xhs_web:current
  docker compose up -d web
  wait_until_ready
}

if docker image inspect xhs_web:current >/dev/null 2>&1; then
  log "Snapshot current image to xhs_web:rollback"
  docker image tag xhs_web:current xhs_web:rollback
else
  log "No existing xhs_web:current image, first deployment mode."
fi

if [[ "${SKIP_BUILD}" != "1" ]]; then
  log "Build web image"
  docker compose build web
else
  log "Skip build (SKIP_BUILD=1)"
fi

log "Restart web container in guardian mode"
docker compose up -d web

if wait_until_ready; then
  if [[ -x "${ROOT_DIR}/scripts/search_stability_watchdog.sh" ]]; then
    nohup "${ROOT_DIR}/scripts/search_stability_watchdog.sh" --daemon >"${WATCHDOG_LOG_FILE}" 2>&1 || true
    log "Search watchdog started (${WATCHDOG_LOG_FILE})"
  fi
  log "Deployment succeeded."
  exit 0
fi

log "Deployment failed, start fail-fast rollback."
if rollback; then
  log "Rollback succeeded."
  exit 1
fi

log "Rollback failed, manual intervention required."
exit 2
