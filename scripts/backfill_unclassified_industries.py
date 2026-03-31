from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings
from app.db import SessionLocal
from app.services.industry_catalog import match_note_industries


def _state_file(namespace: str, shards: int, shard_index: int) -> Path:
    safe_namespace = namespace.strip() or "manual"
    return Path(f"/tmp/xhs_industry_backfill_cursor_{safe_namespace}_{shards}_{shard_index}.txt")


def _load_cursor(path: Path) -> tuple[str, str] | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    parts = raw.split("|", 1)
    if len(parts) != 2:
        return None
    created_at, note_id = parts
    if not created_at or not note_id:
        return None
    return created_at, note_id


def _save_cursor(path: Path, created_at: datetime, note_id: str) -> None:
    path.write_text(f"{created_at.isoformat()}|{note_id}", encoding="utf-8")


def _count_unclassified() -> int:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT
                    GREATEST(
                        0,
                        (SELECT COUNT(*) FROM xhs_note_fact)
                        - (SELECT COUNT(DISTINCT note_id) FROM xhs_note_industry_rel)
                    )::bigint AS unclassified_total
                """
            )
        ).mappings().first()
        return int((row or {}).get("unclassified_total") or 0)
    finally:
        db.close()


def run_backfill_batch(
    *,
    limit: int,
    shards: int = 1,
    shard_index: int = 0,
    namespace: str = "manual",
    reset_cursor: bool = False,
) -> dict[str, Any]:
    safe_shards = max(1, int(shards))
    safe_shard_index = max(0, min(int(shard_index), safe_shards - 1))
    safe_limit = max(50, int(limit))

    state_path = _state_file(namespace, safe_shards, safe_shard_index)
    if reset_cursor and state_path.exists():
        state_path.unlink()

    cursor = _load_cursor(state_path)
    cursor_created_at = cursor[0] if cursor else None
    cursor_note_id = cursor[1] if cursor else None

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                WITH candidates AS (
                    SELECT
                        f.note_id,
                        f.search_keyword,
                        f.title,
                        f.content,
                        f.tags,
                        f.created_at,
                        COALESCE(
                            ARRAY_AGG(DISTINCT rel.brand_name) FILTER (WHERE rel.brand_name IS NOT NULL),
                            ARRAY[]::text[]
                        ) AS brand_aliases
                    FROM xhs_note_fact f
                    LEFT JOIN xhs_note_brand_rel rel ON rel.note_id = f.note_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM xhs_note_industry_rel nir
                        WHERE nir.note_id = f.note_id
                    )
                      AND (
                        :shards <= 1
                        OR MOD(ABS(hashtext(f.note_id)), :shards) = :shard_index
                      )
                      AND (
                        CAST(:cursor_created_at AS timestamptz) IS NULL
                        OR f.created_at < CAST(:cursor_created_at AS timestamptz)
                        OR (
                            f.created_at = CAST(:cursor_created_at AS timestamptz)
                            AND f.note_id < CAST(:cursor_note_id AS text)
                        )
                      )
                    GROUP BY f.note_id, f.search_keyword, f.title, f.content, f.tags, f.created_at
                    ORDER BY f.created_at DESC, f.note_id DESC
                    LIMIT :limit
                )
                SELECT *
                FROM candidates
                ORDER BY created_at DESC, note_id DESC
                """
            ),
            {
                "shards": safe_shards,
                "shard_index": safe_shard_index,
                "cursor_created_at": cursor_created_at,
                "cursor_note_id": cursor_note_id,
                "limit": safe_limit,
            },
        ).mappings().all()

        scanned = len(rows)
        matched = 0
        last_cursor_created_at: datetime | None = None
        last_cursor_note_id = ""

        for row in rows:
            row_matched = match_note_industries(
                db,
                note_id=str(row.get("note_id") or ""),
                search_keyword=str(row.get("search_keyword") or ""),
                title=str(row.get("title") or ""),
                content=str(row.get("content") or ""),
                tags=row.get("tags") or [],
                brand_aliases=row.get("brand_aliases") or [],
            )
            matched += int(row_matched)
            last_cursor_created_at = row.get("created_at")
            last_cursor_note_id = str(row.get("note_id") or "")

        db.commit()

        if scanned > 0 and last_cursor_created_at and last_cursor_note_id:
            _save_cursor(state_path, last_cursor_created_at, last_cursor_note_id)

        return {
            "scanned": scanned,
            "matched": matched,
            "cursor_path": str(state_path),
            "done": scanned == 0,
            "shards": safe_shards,
            "shard_index": safe_shard_index,
        }
    finally:
        db.close()


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=settings.industry_classify_backfill_batch_size)
    parser.add_argument("--shards", type=int, default=settings.industry_classify_backfill_shards)
    parser.add_argument("--shard-index", type=int, default=settings.industry_classify_backfill_shard_index)
    parser.add_argument("--namespace", type=str, default="manual")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--reset-cursor", action="store_true")
    args = parser.parse_args()

    while True:
        result = run_backfill_batch(
            limit=args.limit,
            shards=args.shards,
            shard_index=args.shard_index,
            namespace=args.namespace,
            reset_cursor=args.reset_cursor,
        )
        args.reset_cursor = False
        unclassified_total = _count_unclassified()
        print(
            "[industry-backfill] "
            f"scanned={result['scanned']} "
            f"matched={result['matched']} "
            f"unclassified_total={unclassified_total} "
            f"shards={result['shards']} "
            f"shard_index={result['shard_index']} "
            f"cursor_path={result['cursor_path']}"
        )

        if not args.loop:
            break
        sleep_seconds = max(5, int(args.interval_seconds))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
