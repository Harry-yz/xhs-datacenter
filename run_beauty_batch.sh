#!/usr/bin/env bash
set -e

cd /opt/xhs_data_center

LIMIT="${1:-5}"

docker compose exec -T fastapi python /app/scripts/crawl_xhs_beauty.py crawl_keywords --limit "$LIMIT"
