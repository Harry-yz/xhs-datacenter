#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_BASE="${WEB_BASE:-http://127.0.0.1:3210}"
WEB_PAGE_PATH="${WEB_PAGE_PATH:-/zh/datacenter/xhs}"
TIMEOUT="${TIMEOUT:-20}"
WEB_BUILD_DIR="${WEB_BUILD_DIR:-${ROOT_DIR}/web/.next}"

pass() {
  printf '[web-static][pass] %s\n' "$1"
}

fail() {
  printf '[web-static][fail] %s\n' "$1" >&2
}

probe_asset() {
  local path="$1"
  local label="$2"
  local encoded_path="${path//[/%5B}"
  encoded_path="${encoded_path//]/%5D}"
  if curl -fsS --max-time "$TIMEOUT" "${WEB_BASE}${encoded_path}" >/dev/null; then
    pass "${label} ${path}"
  else
    fail "${label} ${path}"
    return 1
  fi
}

manifest_file="${WEB_BUILD_DIR}/app-build-manifest.json"
css_assets=()
js_assets=()

if [[ -f "${manifest_file}" ]]; then
  mapfile -t css_assets < <(python3 - "${manifest_file}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)

seen = set()
for assets in payload.get("pages", {}).values():
    for asset in assets:
        if asset.endswith(".css") and asset not in seen:
            seen.add(asset)
            print(f"/_next/{asset}")
PY
)
  mapfile -t js_assets < <(python3 - "${manifest_file}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)

seen = set()
for assets in payload.get("pages", {}).values():
    for asset in assets:
        if asset.endswith(".js") and asset not in seen:
            seen.add(asset)
            print(f"/_next/{asset}")
PY
)
fi

if [[ ${#css_assets[@]} -eq 0 || ${#js_assets[@]} -eq 0 ]]; then
  page_html="$(curl -fsS --max-time "$TIMEOUT" "${WEB_BASE}${WEB_PAGE_PATH}")"
  if [[ -z "${page_html}" ]]; then
    fail "empty html from ${WEB_BASE}${WEB_PAGE_PATH}"
    exit 1
  fi
  mapfile -t css_assets < <(printf '%s' "${page_html}" | python3 -c 'import re,sys; html=sys.stdin.read(); [print(m) for m in sorted(set(re.findall(r"/_next/static[^\"'\'' >]+\.css", html)))]')
  mapfile -t js_assets < <(printf '%s' "${page_html}" | python3 -c 'import re,sys; html=sys.stdin.read(); [print(m) for m in sorted(set(re.findall(r"/_next/static[^\"'\'' >]+\.js", html)))]')
fi

if [[ ${#css_assets[@]} -eq 0 ]]; then
  fail "no css assets discovered from ${WEB_PAGE_PATH}"
  exit 1
fi

if [[ ${#js_assets[@]} -eq 0 ]]; then
  fail "no js assets discovered from ${WEB_PAGE_PATH}"
  exit 1
fi

page_js_asset=""
for asset in "${js_assets[@]}"; do
  if [[ "${asset}" == *"/app/"*"/datacenter/xhs/page-"* ]] && [[ "${asset}" != *"/_not-found/"* ]]; then
    page_js_asset="${asset}"
    break
  fi
done
if [[ -z "${page_js_asset}" ]]; then
  for asset in "${js_assets[@]}"; do
    if [[ "${asset}" == *"/app/"*"/page-"* ]] && [[ "${asset}" != *"/_not-found/"* ]]; then
      page_js_asset="${asset}"
      break
    fi
  done
fi
if [[ -z "${page_js_asset}" ]]; then
  for asset in "${js_assets[@]}"; do
    if [[ "${asset}" == *"/main-app-"* ]] || [[ "${asset}" == *"/webpack-"* ]]; then
      page_js_asset="${asset}"
      break
    fi
  done
fi
if [[ -z "${page_js_asset}" ]]; then
  for asset in "${js_assets[@]}"; do
    if [[ "${asset}" != *"/_not-found/"* ]]; then
      page_js_asset="${asset}"
      break
    fi
  done
fi
if [[ -z "${page_js_asset}" ]]; then
  page_js_asset="${js_assets[0]}"
fi

probe_asset "${css_assets[0]}" "css asset"
probe_asset "${page_js_asset}" "js asset"

pass "static asset checks passed for ${WEB_PAGE_PATH}"
