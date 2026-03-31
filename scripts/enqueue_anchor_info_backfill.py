from __future__ import annotations

import argparse
from sqlalchemy import text

from app.db import SessionLocal
from app.tasks.jobs import trigger_anchor_info
from scripts.enqueue_utils import dispatch_staggered, normalize_limit, resolve_enqueue_capacity


def main(
    limit: int = 200,
    cooldown_hours: int = 24,
    recent_hours: int | None = None,
    min_like: int = 100,
    min_interaction: int = 300,
    max_pending: int = 20,
    spacing_seconds: int = 30,
    pause_every: int = 5,
    pause_seconds: float = 2.0,
) -> int:
    db = SessionLocal()
    try:
        recent_hours_filter = recent_hours or 0
        min_like_filter = min_like or 0
        min_interaction_filter = min_interaction or 0
        effective_limit, pending = resolve_enqueue_capacity(
            db,
            task_type="anchor_info",
            requested_limit=limit,
            max_pending=max_pending,
        )
        print(f"pending_anchor_info={pending} max_pending={max_pending} effective_limit={effective_limit}")
        if effective_limit <= 0:
            print("skip_enqueue_anchor_info=true")
            return 0

        sql_limit = normalize_limit(effective_limit)

        rows = db.execute(
            text(
                """
                WITH author_signal AS (
                    SELECT
                        f.author_id,
                        MAX(COALESCE(f.like_count, 0)) AS max_like_count,
                        MAX(
                            COALESCE(f.like_count, 0)
                          + COALESCE(f.collection_count, 0)
                          + COALESCE(f.comment_count, 0)
                          + COALESCE(f.share_count, 0)
                        ) AS max_interaction_total,
                        COUNT(*) FILTER (WHERE COALESCE(f.like_count, 0) >= :min_like) AS qualifying_note_count,
                        MAX(COALESCE(f.publish_time, f.updated_at, f.created_at)) AS latest_note_at
                    FROM xhs_note_fact f
                    WHERE f.author_id IS NOT NULL
                      AND f.author_id <> ''
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
                    GROUP BY f.author_id
                )
                SELECT s.author_id
                FROM author_signal s
                LEFT JOIN xhs_anchor_dim a
                  ON a.author_id = s.author_id
                WHERE NOT EXISTS (
                        SELECT 1
                        FROM xhs_crawl_log l
                        WHERE l.task_type = 'anchor_info'
                          AND l.author_id = s.author_id
                          AND l.created_at >= now() - (:cooldown_hours || ' hour')::interval
                )
                ORDER BY
                    CASE WHEN COALESCE(a.fans_count, 0) = 0 THEN 0 ELSE 1 END ASC,
                    s.max_like_count DESC,
                    s.max_interaction_total DESC,
                    s.qualifying_note_count DESC,
                    s.latest_note_at DESC,
                    s.author_id ASC
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

        print(f"need_anchor_backfill={len(rows)}")
        dispatch_staggered(
            trigger_anchor_info,
            rows,
            label="author_id",
            spacing_seconds=spacing_seconds,
            pause_every=pause_every,
            pause_seconds=pause_seconds,
        )
        return len(rows)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--cooldown-hours", type=int, default=24)
    parser.add_argument("--recent-hours", type=int, default=None)
    parser.add_argument("--min-like", type=int, default=100)
    parser.add_argument("--min-interaction", type=int, default=300)
    parser.add_argument("--max-pending", type=int, default=20)
    parser.add_argument("--spacing-seconds", type=int, default=30)
    parser.add_argument("--pause-every", type=int, default=5)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
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
