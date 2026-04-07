#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f "${ROOT_DIR}/.env.preview" ]]; then
  echo ".env.preview is missing" >&2
  exit 1
fi

if ! docker network inspect xhs_data_center_default >/dev/null 2>&1; then
  echo "Docker network xhs_data_center_default was not found. Start the main stack once so the shared network exists." >&2
  exit 1
fi

echo "[preview] starting FastAPI + Web preview stack"
docker compose -f "${ROOT_DIR}/docker-compose.preview.yml" up -d --build fastapi-preview web-preview

echo "[preview] backend: http://127.0.0.1:8100"
echo "[preview] frontend: http://127.0.0.1:3100"
echo "[preview] use: docker compose -f docker-compose.preview.yml logs -f web-preview fastapi-preview"
