from __future__ import annotations

import argparse
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.tasks.jobs import trigger_note_comments
from scripts.enqueue_utils import dispatch_staggered, normalize_limit, resolve_enqueue_capacity


def main(
    limit: int = 300,
    cooldown_hours: int = 24,
    recent_hours: int | None = None,
    min_like: int = 100,
    min_interaction: int = 300,
    max_pending: int = 30,
    spacing_seconds: int = 20,
    pause_every: int = 5,
    pause_seconds: float = 1.5,
) -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        recent_hours_filter = recent_hours or 0
        min_like_filter = min_like or 0
        min_interaction_filter = min_interaction or 0
        effective_limit, pending = resolve_enqueue_capacity(
            db,
            task_type="note_comment",
            requested_limit=limit,
            max_pending=max_pending,
        )
        print(f"pending_note_comment={pending} max_pending={max_pending} effective_limit={effective_limit}")
        if effective_limit <= 0:
            print("skip_enqueue_note_comment=true")
            return 0

        limit_error_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM xhs_crawl_log
                    WHERE task_type = 'note_comment'
                      AND status = 'failed'
                      AND created_at >= now() - (:window_minutes || ' minute')::interval
                      AND (
                            COALESCE(error_msg, '') ILIKE '%当前任务已达上限%'
                         OR COALESCE(error_msg, '') ILIKE '%任务已达上限%'
                         OR COALESCE(error_msg, '') ILIKE '%task limit%'
                         OR COALESCE(error_msg, '') ILIKE '%reached the limit%'
                         OR COALESCE(response_payload::text, '') ILIKE '%当前任务已达上限%'
                         OR COALESCE(response_payload::text, '') ILIKE '%任务已达上限%'
                         OR COALESCE(response_payload::text, '') ILIKE '%task limit%'
                         OR COALESCE(response_payload::text, '') ILIKE '%reached the limit%'
                      )
                    """
                ),
                {"window_minutes": max(5, settings.huitun_limit_guard_window_minutes)},
            ).scalar()
            or 0
        )
        if limit_error_count >= max(10, settings.huitun_limit_guard_threshold):
            print(
                "skip_enqueue_note_comment=true "
                f"reason=provider_limit_guard "
                f"limit_error_count={limit_error_count}"
            )
            return 0

        sql_limit = normalize_limit(effective_limit)

        rows = db.execute(
            text(
                """
                SELECT f.note_id
                FROM xhs_note_fact f
                WHERE f.note_id IS NOT NULL
                  AND f.note_id <> ''
                  AND (:recent_hours = 0 OR f.updated_at >= now() - (:recent_hours || ' hour')::interval)
                  AND (
                        COALESCE(f.like_count, 0) >= :min_like
                     OR (
                            COALESCE(f.like_count, 0)
                          + COALESCE(f.collection_count, 0)
                          + COALESCE(f.comment_count, 0)
                          + COALESCE(f.share_count, 0)
                        ) >= :min_interaction
                  )
                  AND NOT EXISTS (
                        SELECT 1
                        FROM xhs_crawl_log l
                        WHERE l.task_type = 'note_comment'
                          AND l.note_id = f.note_id
                          AND l.created_at >= now() - (:cooldown_hours || ' hour')::interval
                  )
                ORDER BY
                    COALESCE(f.like_count, 0) DESC,
                    (
                        COALESCE(f.like_count, 0)
                      + COALESCE(f.collection_count, 0)
                      + COALESCE(f.comment_count, 0)
                      + COALESCE(f.share_count, 0)
                    ) DESC,
                    COALESCE(f.publish_time, f.created_at) DESC
                LIMIT :limit
                """
            ),
            {
                "limit": sql_limit,
                "cooldown_hours": cooldown_hours,
                "recent_hours": recent_hours_filter,
                "min_like": min_like_filter,
                "min_interaction": min_interaction_filter,
            },
        ).scalars().all()

        print(f"need_comment_backfill={len(rows)}")
        dispatch_staggered(
            trigger_note_comments,
            rows,
            label="note_id",
            spacing_seconds=spacing_seconds,
            pause_every=pause_every,
            pause_seconds=pause_seconds,
        )
        return len(rows)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--cooldown-hours", type=int, default=24)
    parser.add_argument("--recent-hours", type=int, default=None)
    parser.add_argument("--min-like", type=int, default=100)
    parser.add_argument("--min-interaction", type=int, default=300)
    parser.add_argument("--max-pending", type=int, default=30)
    parser.add_argument("--spacing-seconds", type=int, default=20)
    parser.add_argument("--pause-every", type=int, default=5)
    parser.add_argument("--pause-seconds", type=float, default=1.5)
    args = parser.parse_args()

    main(
        limit=args.limit,
        cooldown_hours=args.cooldown_hours,
        recent_hours=args.recent_hours,
        min_like=args.min_like,
        min_interaction=args.min_interaction,
        max_pending=args.max_pending,
        spacing_seconds=args.spacing_seconds,
        pause_every=args.pause_every,
        pause_seconds=args.pause_seconds,
    )
