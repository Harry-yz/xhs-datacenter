#!/usr/bin/env bash
set -e

cd /opt/xhs_data_center

echo "==> 1. sync beauty catalog"
docker compose exec -T fastapi python /app/scripts/sync_beauty_catalog.py

echo "==> 2. keyword search"
docker compose exec -T fastapi python /app/scripts/crawl_xhs_beauty.py crawl_keywords --limit 5

echo "==> 3. backfill note info"
docker compose exec -T fastapi python /app/scripts/enqueue_note_info_backfill.py --limit 20 --cooldown-hours 48 --max-pending 20 --spacing-seconds 15 --pause-every 5 --pause-seconds 2

echo "==> 4. backfill note comments (100+ likes)"
docker compose exec -T fastapi python /app/scripts/enqueue_note_comment_backfill.py --limit 5 --cooldown-hours 72 --min-like 100 --min-interaction 300 --max-pending 5 --spacing-seconds 45 --pause-every 2 --pause-seconds 2

echo "==> 5. backfill anchor info (100+ likes)"
docker compose exec -T fastapi python /app/scripts/enqueue_anchor_info_backfill.py --limit 3 --cooldown-hours 72 --min-like 100 --min-interaction 300 --max-pending 3 --spacing-seconds 60 --pause-every 1 --pause-seconds 2

echo "==> done"
