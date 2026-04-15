#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:3210}"
WEB_HOME_PATH="${WEB_HOME_PATH:-/zh/datacenter/xhs}"
WEB_SEARCH_PATH="${WEB_SEARCH_PATH:-/zh/datacenter/xhs/search?type=category&q=YSL}"
TIMEOUT="${TIMEOUT:-5}"
STATIC_CHECK_PAGE="${STATIC_CHECK_PAGE:-/zh/datacenter/xhs}"

pass() {
  printf '[health][pass] %s\n' "$1"
}

fail() {
  printf '[health][fail] %s\n' "$1" >&2
}

probe_http() {
  local url="$1"
  local label="$2"
  if curl -fsS --max-time "$TIMEOUT" "$url" >/dev/null; then
    pass "$label ($url)"
  else
    fail "$label ($url)"
    return 1
  fi
}

probe_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  if timeout "$TIMEOUT" bash -lc "</dev/tcp/${host}/${port}" >/dev/null 2>&1; then
    pass "$label ${host}:${port}"
  else
    fail "$label ${host}:${port}"
    return 1
  fi
}

probe_static_assets() {
  local label="$1"
  local static_timeout="${STATIC_TIMEOUT:-15}"
  if WEB_BASE="${WEB_BASE}" WEB_PAGE_PATH="${STATIC_CHECK_PAGE}" TIMEOUT="${static_timeout}" "${ROOT_DIR}/scripts/check_web_static_assets.sh" >/dev/null; then
    pass "${label} (${WEB_BASE}${STATIC_CHECK_PAGE})"
  else
    fail "${label} (${WEB_BASE}${STATIC_CHECK_PAGE})"
    return 1
  fi
}

probe_search_gate() {
  local payload
  payload="$(curl -fsS --max-time "$TIMEOUT" -X POST "${WEB_BASE}/api/search/brand-category" \
    -H "Content-Type: application/json" \
    --data '{"locale":"zh","query":"YSL","sort":"stat","order":"desc","page":1,"size":30,"min_like":1,"date_range":30,"freshness_hours":24,"force_refresh":false}' || true)"
  if [[ -z "${payload}" ]]; then
    fail "search api gate empty payload"
    return 1
  fi
  if grep -q '"errorType":"upstream_misconfigured"' <<<"${payload}"; then
    fail "search api gate upstream misconfigured"
    return 1
  fi
  if grep -q '"status":"ready"' <<<"${payload}" && grep -q '"noteId":"' <<<"${payload}"; then
    pass "search api gate (YSL ready with items)"
    return 0
  fi
  fail "search api gate not ready with items"
  return 1
}

probe_cold_search_gate() {
  local probe_query payload
  probe_query="cold_probe_$(date +%s)"
  payload="$(curl -fsS --max-time "$TIMEOUT" -X POST "${WEB_BASE}/api/search/brand-category" \
    -H "Content-Type: application/json" \
    --data "{\"locale\":\"zh\",\"query\":\"${probe_query}\",\"sort\":\"stat\",\"order\":\"desc\",\"page\":1,\"size\":30,\"min_like\":1,\"date_range\":30,\"freshness_hours\":24,\"force_refresh\":false}" || true)"
  if [[ -z "${payload}" ]]; then
    fail "cold search gate empty payload"
    return 1
  fi
  if grep -q '"status":"failed"' <<<"${payload}"; then
    fail "cold search gate failed"
    return 1
  fi
  if grep -q '"status":"pending"' <<<"${payload}"; then
    if grep -q '"job_id":"[^"]\+"' <<<"${payload}"; then
      pass "cold search gate (pending with job_id)"
      return 0
    fi
    fail "cold search gate pending without job_id"
    return 1
  fi
  if grep -q '"status":"ready"' <<<"${payload}"; then
    pass "cold search gate (ready)"
    return 0
  fi
  fail "cold search gate unknown status"
  return 1
}

status=0

probe_http "${API_BASE}/health" "api health" || status=1
probe_http "${API_BASE}/api/v1/dashboard/xhs/overview?days=90" "dashboard overview" || status=1
probe_http "${API_BASE}/api/v1/dashboard/xhs/live" "dashboard live" || status=1
probe_http "${WEB_BASE}${WEB_HOME_PATH}" "web xhs home page" || status=1
probe_http "${WEB_BASE}${WEB_SEARCH_PATH}" "web xhs search page" || status=1
probe_static_assets "web static assets" || status=1
probe_search_gate || status=1
probe_cold_search_gate || status=1
probe_port "127.0.0.1" "8000" "api port" || status=1
probe_port "127.0.0.1" "3210" "web port" || status=1

if [[ $status -eq 0 ]]; then
  pass "all checks passed"
else
  fail "one or more checks failed"
fi

exit "$status"
