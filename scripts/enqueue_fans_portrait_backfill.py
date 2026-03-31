from __future__ import annotations

import argparse
from sqlalchemy import text

from app.db import SessionLocal
from app.tasks.jobs import trigger_fans_portrait
from scripts.enqueue_utils import dispatch_staggered, resolve_enqueue_capacity


def main(
    limit: int = 100,
    cooldown_hours: int = 48,
    max_pending: int = 10,
    spacing_seconds: int = 45,
    pause_every: int = 3,
    pause_seconds: float = 2.0,
) -> int:
    db = SessionLocal()
    try:
        effective_limit, pending = resolve_enqueue_capacity(
            db,
            task_type="fans_portrait",
            requested_limit=limit,
            max_pending=max_pending,
        )
        print(f"pending_fans_portrait={pending} max_pending={max_pending} effective_limit={effective_limit}")
        if effective_limit <= 0:
            print("skip_enqueue_fans_portrait=true")
            return 0

        rows = db.execute(
            text(
                """
                SELECT a.author_id
                FROM xhs_anchor_dim a
                WHERE a.author_id IS NOT NULL
                  AND a.author_id <> ''
                  AND a.anchor_link IS NOT NULL
                  AND a.anchor_link <> ''
                  AND NOT EXISTS (
                        SELECT 1
                        FROM xhs_crawl_log l
                        WHERE l.task_type = 'fans_portrait'
                          AND l.author_id = a.author_id
                          AND l.created_at >= now() - (:cooldown_hours || ' hour')::interval
                  )
                ORDER BY COALESCE(a.fans_count, 0) DESC, a.author_id
                LIMIT :limit
                """
            ),
            {
                "limit": effective_limit,
                "cooldown_hours": cooldown_hours,
            },
        ).scalars().all()

        print(f"need_fans_backfill={len(rows)}")
        dispatch_staggered(
            trigger_fans_portrait,
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
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--cooldown-hours", type=int, default=48)
    parser.add_argument("--max-pending", type=int, default=10)
    parser.add_argument("--spacing-seconds", type=int, default=45)
    parser.add_argument("--pause-every", type=int, default=3)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    args = parser.parse_args()
    main(
        limit=args.limit,
        cooldown_hours=args.cooldown_hours,
        max_pending=args.max_pending,
        spacing_seconds=args.spacing_seconds,
        pause_every=args.pause_every,
        pause_seconds=args.pause_seconds,
    )
