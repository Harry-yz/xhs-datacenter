from __future__ import annotations

import argparse
from sqlalchemy import text

from app.db import SessionLocal
from app.tasks.jobs import trigger_note_info
from scripts.enqueue_utils import dispatch_staggered, normalize_limit, resolve_enqueue_capacity


def main(
    limit: int = 100,
    cooldown_hours: int = 24,
    recent_hours: int | None = None,
    min_like: int | None = None,
    min_interaction: int | None = None,
    refresh_all: bool = False,
    max_pending: int = 60,
    spacing_seconds: int = 10,
    pause_every: int = 10,
    pause_seconds: float = 1.0,
) -> int:
    db = SessionLocal()
    try:
        recent_hours_filter = recent_hours or 0
        min_like_filter = min_like or 0
        min_interaction_filter = min_interaction or 0
        effective_limit, pending = resolve_enqueue_capacity(
            db,
            task_type="note_info",
            requested_limit=limit,
            max_pending=max_pending,
        )
        print(f"pending_note_info={pending} max_pending={max_pending} effective_limit={effective_limit}")
        if effective_limit <= 0:
            print("skip_enqueue_note_info=true")
            return 0

        sql_limit = normalize_limit(effective_limit)

        rows = db.execute(
            text(
                """
                WITH search_signal AS (
                    SELECT
                        sr.note_id,
                        COUNT(DISTINCT sr.keyword) AS keyword_hits,
                        MIN(COALESCE(sr.search_rank, 999999)) AS best_search_rank,
                        MAX(sr.created_at) AS latest_search_seen_at
                    FROM xhs_note_search_result sr
                    WHERE sr.note_id IS NOT NULL
                      AND sr.note_id <> ''
                    GROUP BY sr.note_id
                )
                SELECT f.note_id
                FROM xhs_note_fact f
                LEFT JOIN search_signal s
                  ON s.note_id = f.note_id
                WHERE f.note_id IS NOT NULL
                  AND f.note_id <> ''
                  AND (:recent_hours = 0 OR f.updated_at >= now() - (:recent_hours || ' hour')::interval)
                  AND (
                        :min_like = 0
                     OR COALESCE(f.like_count, 0) >= :min_like
                     OR (
                            :min_interaction > 0
                        AND (
                                COALESCE(f.like_count, 0)
                              + COALESCE(f.collection_count, 0)
                              + COALESCE(f.comment_count, 0)
                              + COALESCE(f.share_count, 0)
                            ) >= :min_interaction
                        )
                  )
                  AND (
                        :refresh_all = TRUE
                     OR COALESCE(f.content, '') = ''
                     OR COALESCE(f.read_count, 0) = 0
                     OR COALESCE(f.stat_count, 0) = 0
                     OR COALESCE(f.like_count, 0) = 0
                     OR COALESCE(f.collection_count, 0) = 0
                     OR COALESCE(f.comment_count, 0) = 0
                     OR COALESCE(f.share_count, 0) = 0
                     OR COALESCE(f.author_id, '') = ''
                  )
                  AND NOT EXISTS (
                        SELECT 1
                        FROM xhs_crawl_log l
                        WHERE l.task_type = 'note_info'
                          AND l.note_id = f.note_id
                          AND l.created_at >= now() - (:cooldown_hours || ' hour')::interval
                )
                ORDER BY
                    CASE
                        WHEN COALESCE(f.like_count, 0) = 0
                         AND COALESCE(f.collection_count, 0) = 0
                         AND COALESCE(f.comment_count, 0) = 0
                         AND COALESCE(f.share_count, 0) = 0
                         AND COALESCE(f.read_count, 0) = 0
                        THEN 0
                        ELSE 1
                    END ASC,
                    COALESCE(s.keyword_hits, 0) DESC,
                    COALESCE(s.best_search_rank, 999999) ASC,
                    COALESCE(f.like_count, 0) DESC,
                    (
                        COALESCE(f.like_count, 0)
                      + COALESCE(f.collection_count, 0)
                      + COALESCE(f.comment_count, 0)
                      + COALESCE(f.share_count, 0)
                    ) DESC,
                    COALESCE(s.latest_search_seen_at, f.publish_time, f.created_at) DESC
                LIMIT :limit
                """
            ),
            {
                "limit": sql_limit,
                "cooldown_hours": cooldown_hours,
                "recent_hours": recent_hours_filter,
                "min_like": min_like_filter,
                "min_interaction": min_interaction_filter,
                "refresh_all": refresh_all,
            },
        ).scalars().all()

        print(f"need_note_info_backfill={len(rows)}")
        dispatch_staggered(
            trigger_note_info,
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
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--cooldown-hours", type=int, default=24)
    parser.add_argument("--recent-hours", type=int, default=None)
    parser.add_argument("--min-like", type=int, default=None)
    parser.add_argument("--min-interaction", type=int, default=None)
    parser.add_argument("--refresh-all", action="store_true")
    parser.add_argument("--max-pending", type=int, default=60)
    parser.add_argument("--spacing-seconds", type=int, default=10)
    parser.add_argument("--pause-every", type=int, default=10)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    main(
        limit=args.limit,
        cooldown_hours=args.cooldown_hours,
        recent_hours=args.recent_hours,
        min_like=args.min_like,
        min_interaction=args.min_interaction,
        refresh_all=args.refresh_all,
        max_pending=args.max_pending,
        spacing_seconds=args.spacing_seconds,
        pause_every=args.pause_every,
        pause_seconds=args.pause_seconds,
    )
