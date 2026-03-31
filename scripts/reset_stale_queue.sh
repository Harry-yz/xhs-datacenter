#!/usr/bin/env bash
set -euo pipefail

cd /opt/xhs_data_center

echo "==> stop worker"
docker compose stop worker >/dev/null 2>&1 || true

echo "==> mark stale running tasks as failed"
docker compose exec -T fastapi python - <<'PY'
from sqlalchemy import text
from app.db import SessionLocal

db = SessionLocal()
try:
    result = db.execute(
        text(
            """
            UPDATE xhs_crawl_log
            SET status = 'failed',
                error_msg = COALESCE(error_msg, 'manually cleared stale queue before low-frequency restart'),
                updated_at = now()
            WHERE status = 'running'
              AND COALESCE(is_callback_received, false) = false
              AND task_type IN ('note_info', 'note_comment', 'anchor_info', 'fans_portrait')
            """
        )
    )
    db.commit()
    print({"updated_rows": result.rowcount})
finally:
    db.close()
PY

echo "==> clear stale redis queue state"
docker compose exec -T redis redis-cli DEL xhs_queue unacked unacked_index >/dev/null

echo "==> queue status"
docker compose exec -T redis redis-cli LLEN xhs_queue
