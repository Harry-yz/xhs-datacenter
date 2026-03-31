from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.services.brand_recognition import sync_brand_dictionary, sync_note_brand_relations


def main(
    *,
    limit: int = 0,
    min_like: int = 0,
    refresh_existing: bool = True,
    recent_hours: int | None = None,
) -> dict[str, int]:
    db = SessionLocal()
    try:
        brand_count = sync_brand_dictionary(db)
        matched_count = sync_note_brand_relations(
            db,
            limit=limit or None,
            min_like=min_like,
            refresh_existing=refresh_existing,
            recent_hours=recent_hours,
        )
        return {
            "brand_seed_count": brand_count,
            "matched_relation_count": matched_count,
        }
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-like", type=int, default=0)
    parser.add_argument("--recent-hours", type=int, default=0)
    parser.add_argument("--no-refresh", action="store_true")
    args = parser.parse_args()
    result = main(
        limit=args.limit,
        min_like=args.min_like,
        refresh_existing=not args.no_refresh,
        recent_hours=args.recent_hours or None,
    )
    print(result)
