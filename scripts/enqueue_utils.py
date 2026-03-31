from __future__ import annotations

import time
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

UNBOUNDED_LIMIT = 2147483647


def normalize_limit(value: int | None) -> int:
    if value is None or value <= 0:
        return UNBOUNDED_LIMIT
    return value


def count_recent_pending_tasks(
    db: Session,
    *,
    task_type: str,
    lookback_hours: int = 48,
) -> int:
    return int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM xhs_crawl_log
                WHERE task_type = :task_type
                  AND status = 'running'
                  AND COALESCE(is_callback_received, false) = false
                  AND created_at >= now() - (:lookback_hours || ' hour')::interval
                """
            ),
            {
                "task_type": task_type,
                "lookback_hours": lookback_hours,
            },
        ).scalar()
        or 0
    )


def resolve_enqueue_capacity(
    db: Session,
    *,
    task_type: str,
    requested_limit: int,
    max_pending: int,
    lookback_hours: int = 48,
) -> tuple[int, int]:
    pending = count_recent_pending_tasks(
        db,
        task_type=task_type,
        lookback_hours=lookback_hours,
    )
    normalized_requested_limit = normalize_limit(requested_limit)
    if max_pending <= 0:
        return normalized_requested_limit, pending

    available = max(0, max_pending - pending)
    return min(normalized_requested_limit, available), pending


def dispatch_staggered(
    task,
    identifiers: Sequence[str],
    *,
    label: str,
    spacing_seconds: int,
    pause_every: int,
    pause_seconds: float,
) -> int:
    items = [str(identifier) for identifier in identifiers if str(identifier).strip()]

    for idx, identifier in enumerate(items, start=1):
        countdown = max(0, (idx - 1) * spacing_seconds)
        result = task.apply_async(args=[identifier], countdown=countdown)
        print(f"{idx}. {label}={identifier} task_id={result.id} countdown={countdown}s")

        if pause_every > 0 and pause_seconds > 0 and idx % pause_every == 0 and idx < len(items):
            time.sleep(pause_seconds)

    return len(items)
