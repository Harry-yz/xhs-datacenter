#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

WEB_BASE="${WEB_BASE:-http://127.0.0.1:3210}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
WATCHDOG_PID_FILE="${WATCHDOG_PID_FILE:-/tmp/xhs_search_watchdog.pid}"
WATCHDOG_STATE_FILE="${WATCHDOG_STATE_FILE:-/tmp/xhs_search_watchdog.state}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-60}"
RESTART_COOLDOWN_SECONDS="${RESTART_COOLDOWN_SECONDS:-300}"
AUTO_CLEANUP_ENABLED="${AUTO_CLEANUP_ENABLED:-1}"
AUTO_CLEANUP_COOLDOWN_SECONDS="${AUTO_CLEANUP_COOLDOWN_SECONDS:-21600}"
DISK_WARN_THRESHOLD="${DISK_WARN_THRESHOLD:-85}"
DISK_CLEAN_THRESHOLD="${DISK_CLEAN_THRESHOLD:-92}"
MISCONFIG_THRESHOLD="${MISCONFIG_THRESHOLD:-2}"
TIMEOUT_THRESHOLD="${TIMEOUT_THRESHOLD:-6}"
PENDING_RATE_THRESHOLD="${PENDING_RATE_THRESHOLD:-0.8}"
JOB_BACKLOG_WARN_THRESHOLD="${JOB_BACKLOG_WARN_THRESHOLD:-10000}"

MODE="once"
if [[ "${1:-}" == "--daemon" ]]; then
  MODE="daemon"
fi

log() {
  printf '[search-watchdog] %s\n' "$1"
}

json_get() {
  local key="$1"
  python3 - "$key" <<'PY'
import json
import sys

key = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    print("")
    raise SystemExit(0)
try:
    payload = json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)

cur = payload
for part in key.split('.'):
    if isinstance(cur, dict):
        cur = cur.get(part)
    else:
        cur = None
        break
if cur is None:
    print("")
elif isinstance(cur, bool):
    print("true" if cur else "false")
else:
    print(str(cur))
PY
}

check_query() {
  local query="$1"
  local payload
  payload="$(docker compose exec -T fastapi /bin/sh -lc "curl -sS --max-time 20 -X POST ${API_BASE}/api/v1/search/brand-category -H 'Content-Type: application/json' --data '{\"query\":\"${query}\",\"mode\":\"category\",\"sort\":\"stat\",\"order\":\"desc\",\"page\":1,\"size\":30,\"min_like\":1,\"date_range\":30,\"freshness_hours\":24,\"force_refresh\":false}'" 2>/dev/null || true)"

  if [[ -z "${payload}" ]]; then
    echo "error|empty"
    return
  fi
  local status
  status="$(printf '%s' "${payload}" | json_get 'data.status' | tr -d '\r' | xargs)"
  if [[ "${status}" == "pending" || "${status}" == "running" ]]; then
    echo "pending|${query}"
    return
  fi
  if [[ "${status}" == "failed" ]]; then
    echo "failed|${query}"
    return
  fi

  local total
  total="$(printf '%s' "${payload}" | json_get 'data.pagination.total' | tr -d '\r' | xargs)"
  if [[ -n "${total}" ]] && [[ "${total}" =~ ^[0-9]+$ ]] && (( total > 0 )); then
    echo "ready|${query}"
    return
  fi

  if [[ "${status}" == "ready" ]] && grep -q '"note_id":"' <<<"${payload}"; then
    echo "ready|${query}"
    return
  fi

  echo "empty|${query}"
}

query_job_backlog() {
  if ! command -v psql >/dev/null 2>&1; then
    echo "-1"
    return
  fi
  if [[ ! -f "${ROOT_DIR}/.env" ]]; then
    echo "-1"
    return
  fi

  # shellcheck disable=SC1090
  source <(tr -d '\r' < "${ROOT_DIR}/.env")
  if [[ -z "${DB_HOST:-}" || -z "${DB_PORT:-}" || -z "${DB_USER:-}" || -z "${DB_PASSWORD:-}" || -z "${DB_NAME:-}" ]]; then
    echo "-1"
    return
  fi

  PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -Atc \
    "select count(*) from xhs_search_job where status in ('pending','running');" 2>/dev/null || echo "-1"
}

read_last_restart_at() {
  if [[ ! -f "${WATCHDOG_STATE_FILE}" ]]; then
    echo "0"
    return
  fi
  awk -F= '/^last_restart_at=/{print $2}' "${WATCHDOG_STATE_FILE}" | tail -n 1
}

read_last_cleanup_at() {
  if [[ ! -f "${WATCHDOG_STATE_FILE}" ]]; then
    echo "0"
    return
  fi
  awk -F= '/^last_cleanup_at=/{print $2}' "${WATCHDOG_STATE_FILE}" | tail -n 1
}

write_last_restart_at() {
  local ts="$1"
  local last_cleanup
  last_cleanup="$(read_last_cleanup_at)"
  if [[ -z "${last_cleanup}" ]]; then
    last_cleanup=0
  fi
  {
    printf 'last_restart_at=%s\n' "${ts}"
    printf 'last_cleanup_at=%s\n' "${last_cleanup}"
  } >"${WATCHDOG_STATE_FILE}"
}

write_last_cleanup_at() {
  local ts="$1"
  local last_restart
  last_restart="$(read_last_restart_at)"
  if [[ -z "${last_restart}" ]]; then
    last_restart=0
  fi
  {
    printf 'last_restart_at=%s\n' "${last_restart}"
    printf 'last_cleanup_at=%s\n' "${ts}"
  } >"${WATCHDOG_STATE_FILE}"
}

restart_web_if_allowed() {
  local reason="$1"
  local now
  now="$(date +%s)"
  local last
  last="$(read_last_restart_at)"
  if [[ -z "${last}" || ! "${last}" =~ ^[0-9]+$ ]]; then
    last=0
  fi
  if (( now - last < RESTART_COOLDOWN_SECONDS )); then
    log "restart skipped (cooldown) reason=${reason}"
    return
  fi

  log "restart web triggered reason=${reason}"
  if docker compose restart web >/dev/null 2>&1; then
    write_last_restart_at "${now}"
    log "restart web done"
  else
    log "restart web failed"
  fi
}

disk_usage_percent() {
  df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5+0}'
}

redis_persistence_status() {
  local info
  info="$(docker compose exec -T redis redis-cli INFO persistence 2>/dev/null || true)"
  if [[ -z "${info}" ]]; then
    echo "unknown|unknown"
    return
  fi
  local rdb_status aof_status
  rdb_status="$(awk -F: '/^rdb_last_bgsave_status:/{gsub(/\r/,"",$2); print $2}' <<<"${info}" | tail -n 1)"
  aof_status="$(awk -F: '/^aof_last_write_status:/{gsub(/\r/,"",$2); print $2}' <<<"${info}" | tail -n 1)"
  echo "${rdb_status:-unknown}|${aof_status:-unknown}"
}

run_safe_cleanup_if_needed() {
  if [[ "${AUTO_CLEANUP_ENABLED}" != "1" ]]; then
    return
  fi
  local usage="$1"
  if (( usage < DISK_CLEAN_THRESHOLD )); then
    return
  fi
  local now last
  now="$(date +%s)"
  last="$(read_last_cleanup_at)"
  if [[ -z "${last}" || ! "${last}" =~ ^[0-9]+$ ]]; then
    last=0
  fi
  if (( now - last < AUTO_CLEANUP_COOLDOWN_SECONDS )); then
    log "safe cleanup skipped (cooldown) disk=${usage}%"
    return
  fi
  if [[ -x "${ROOT_DIR}/scripts/host_safe_cleanup.sh" ]]; then
    log "safe cleanup triggered disk=${usage}%"
    if "${ROOT_DIR}/scripts/host_safe_cleanup.sh" >/tmp/xhs_host_safe_cleanup.log 2>&1; then
      write_last_cleanup_at "${now}"
      log "safe cleanup done"
    else
      log "safe cleanup failed"
    fi
  fi
}

run_once() {
  local queries=("YSL")
  local ready=0
  local pending=0
  local failed=0
  local errors=0

  local outcome
  for q in "${queries[@]}"; do
    outcome="$(check_query "${q}")"
    case "${outcome%%|*}" in
      ready) ready=$((ready + 1)) ;;
      pending) pending=$((pending + 1)) ;;
      failed|empty) failed=$((failed + 1)) ;;
      error) errors=$((errors + 1)) ;;
      *) failed=$((failed + 1)) ;;
    esac
  done

  local pending_rate
  pending_rate="$(python3 - <<PY
ready=${ready}
pending=${pending}
failed=${failed}
total=max(ready+pending+failed,1)
print(pending/total)
PY
)"

  local web_recent_logs
  web_recent_logs="$(docker compose logs --since 70s web 2>/dev/null || true)"
  local misconfigured_hits
  misconfigured_hits="$(grep -E 'upstream_misconfigured|upstreamStatus: 405' <<<"${web_recent_logs}" | wc -l | tr -d ' ' || true)"
  local timeout_hits
  timeout_hits="$(grep -E 'upstream_timeout|status 504|TimeoutError' <<<"${web_recent_logs}" | wc -l | tr -d ' ' || true)"

  local backlog
  backlog="$(query_job_backlog)"
  local disk_usage
  disk_usage="$(disk_usage_percent)"
  local redis_state rdb_status aof_status
  redis_state="$(redis_persistence_status)"
  rdb_status="${redis_state%%|*}"
  aof_status="${redis_state##*|}"

  log "ready=${ready} pending=${pending} failed=${failed} errors=${errors} pending_rate=${pending_rate} misconfigured=${misconfigured_hits} timeout=${timeout_hits} backlog=${backlog} disk=${disk_usage}% redis_rdb=${rdb_status} redis_aof=${aof_status}"

  if (( errors > 0 )); then
    log "warning query probe errors=${errors}"
  elif (( misconfigured_hits >= MISCONFIG_THRESHOLD )); then
    restart_web_if_allowed "misconfigured_${misconfigured_hits}"
  elif (( timeout_hits >= TIMEOUT_THRESHOLD )); then
    restart_web_if_allowed "timeout_${timeout_hits}"
  else
    local pending_alert
    pending_alert="$(python3 - <<PY
rate=float('${pending_rate}')
print('1' if rate >= float('${PENDING_RATE_THRESHOLD}') else '0')
PY
)"
    if [[ "${pending_alert}" == "1" ]] && (( ready == 0 )); then
      restart_web_if_allowed "high_pending_rate_${pending_rate}"
    fi
  fi

  if [[ "${backlog}" =~ ^[0-9]+$ ]] && (( backlog >= JOB_BACKLOG_WARN_THRESHOLD )); then
    log "warning backlog high: ${backlog}"
  fi

  if [[ "${disk_usage}" =~ ^[0-9]+$ ]] && (( disk_usage >= DISK_WARN_THRESHOLD )); then
    log "warning disk usage high: ${disk_usage}%"
    run_safe_cleanup_if_needed "${disk_usage}"
  fi

  if [[ "${rdb_status}" != "ok" || "${aof_status}" != "ok" ]]; then
    log "warning redis persistence abnormal: rdb=${rdb_status} aof=${aof_status}"
  fi

  if docker compose exec -T fastapi /bin/sh -lc "curl -fsS ${API_BASE}/health >/dev/null" >/dev/null 2>&1; then
    :
  else
    log "warning api health probe failed"
  fi
}

if [[ "${MODE}" == "daemon" ]]; then
  if [[ -f "${WATCHDOG_PID_FILE}" ]] && kill -0 "$(cat "${WATCHDOG_PID_FILE}")" >/dev/null 2>&1; then
    log "daemon already running pid=$(cat "${WATCHDOG_PID_FILE}")"
    exit 0
  fi
  echo "${BASHPID}" >"${WATCHDOG_PID_FILE}"
  trap 'rm -f "${WATCHDOG_PID_FILE}"' EXIT
  log "daemon started pid=${BASHPID}"
  while true; do
    run_once
    sleep "${CHECK_INTERVAL_SECONDS}"
  done
else
  run_once
fi
