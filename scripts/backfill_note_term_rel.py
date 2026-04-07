from __future__ import annotations

import argparse
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.services.search_center import (
    ensure_search_tables,
    get_term_rel_coverage_stats,
    process_note_change_log,
)


def _enqueue_missing_note_terms(db: Session, *, batch_size: int, source: str) -> int:
    rows = db.execute(
        text(
            """
            WITH missing AS (
                SELECT f.note_id
                FROM xhs_note_fact f
                WHERE f.note_id IS NOT NULL
                  AND f.note_id <> ''
                  AND NOT EXISTS (
                        SELECT 1
                        FROM xhs_note_term_rel r
                        WHERE r.note_id = f.note_id
                  )
                ORDER BY COALESCE(f.updated_at, f.created_at, f.publish_time) DESC NULLS LAST, f.note_id
                LIMIT :limit
            )
            INSERT INTO xhs_note_change_log(note_id, change_source, changed_at)
            SELECT m.note_id, :source, now()
            FROM missing m
            ON CONFLICT (note_id) WHERE processed_at IS NULL
            DO UPDATE SET
                change_source = EXCLUDED.change_source,
                changed_at = EXCLUDED.changed_at
            RETURNING note_id
            """
        ),
        {"limit": max(1, int(batch_size)), "source": source[:64]},
    ).scalars().all()
    return len(rows)


def _process_incremental_rounds(
    db: Session,
    *,
    rounds: int,
    process_batch_size: int,
    timeout_ms: int,
) -> dict[str, int]:
    totals = {"changes": 0, "notes": 0, "authors": 0, "terms": 0}
    for _ in range(max(0, rounds)):
        effective_timeout_ms = max(1000, int(timeout_ms))
        db.execute(text(f"SET LOCAL statement_timeout = {effective_timeout_ms}"))
        result = process_note_change_log(db, batch_size=max(1, int(process_batch_size)))
        changes = int(result.get("changes") or 0)
        if changes <= 0:
            break
        totals["changes"] += changes
        totals["notes"] += int(result.get("notes") or 0)
        totals["authors"] += int(result.get("authors") or 0)
        totals["terms"] += int(result.get("terms") or 0)
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill xhs_note_term_rel for notes missing inverted-index terms.")
    parser.add_argument("--enqueue-batch-size", type=int, default=5000)
    parser.add_argument("--max-enqueue", type=int, default=0, help="0 means no limit")
    parser.add_argument("--max-seconds", type=int, default=0, help="0 means no time limit")
    parser.add_argument("--source", type=str, default="term_rel_backfill")
    parser.add_argument("--process-rounds", type=int, default=8)
    parser.add_argument("--process-batch-size", type=int, default=0, help="0 means use SEARCH_INCREMENTAL_BATCH_SIZE")
    parser.add_argument("--process-timeout-ms", type=int, default=12000)
    parser.add_argument("--sleep-ms", type=int, default=80)
    args = parser.parse_args()

    settings = get_settings()
    process_batch_size = (
        max(1, int(args.process_batch_size))
        if int(args.process_batch_size) > 0
        else max(1, int(settings.search_incremental_batch_size))
    )

    started_at = time.monotonic()
    total_enqueued = 0
    total_processed = {"changes": 0, "notes": 0, "authors": 0, "terms": 0}
    cycles = 0

    db = SessionLocal()
    try:
        ensure_search_tables(db)
        db.commit()
        before = get_term_rel_coverage_stats(db)
        print(
            "[backfill-term-rel] start "
            f"term_rel_note_total={before['term_note_total']} "
            f"note_total={before['note_total']} "
            f"coverage_ratio={before['coverage_ratio']:.4f} "
            f"change_log_pending={before['change_log_pending']}"
        )

        while True:
            if args.max_seconds > 0 and (time.monotonic() - started_at) >= int(args.max_seconds):
                print("[backfill-term-rel] stop reason=max_seconds_reached")
                break
            if args.max_enqueue > 0 and total_enqueued >= int(args.max_enqueue):
                print("[backfill-term-rel] stop reason=max_enqueue_reached")
                break

            enqueue_limit = max(1, int(args.enqueue_batch_size))
            if args.max_enqueue > 0:
                remaining = int(args.max_enqueue) - total_enqueued
                if remaining <= 0:
                    break
                enqueue_limit = min(enqueue_limit, remaining)

            enqueued = _enqueue_missing_note_terms(db, batch_size=enqueue_limit, source=args.source)
            if enqueued <= 0:
                db.rollback()
                print("[backfill-term-rel] stop reason=no_missing_notes")
                break

            db.commit()
            total_enqueued += enqueued
            cycles += 1

            processed = _process_incremental_rounds(
                db,
                rounds=max(0, int(args.process_rounds)),
                process_batch_size=process_batch_size,
                timeout_ms=max(1000, int(args.process_timeout_ms)),
            )
            if int(processed.get("changes") or 0) > 0:
                db.commit()
            else:
                db.rollback()

            total_processed["changes"] += int(processed.get("changes") or 0)
            total_processed["notes"] += int(processed.get("notes") or 0)
            total_processed["authors"] += int(processed.get("authors") or 0)
            total_processed["terms"] += int(processed.get("terms") or 0)

            print(
                "[backfill-term-rel] cycle_done "
                f"cycle={cycles} "
                f"enqueued={enqueued} "
                f"processed_changes={processed['changes']} "
                f"processed_notes={processed['notes']} "
                f"processed_terms={processed['terms']} "
                f"total_enqueued={total_enqueued}"
            )
            time.sleep(max(0, int(args.sleep_ms)) / 1000)

        after = get_term_rel_coverage_stats(db)
        print(
            "[backfill-term-rel] done "
            f"cycles={cycles} "
            f"total_enqueued={total_enqueued} "
            f"total_processed_changes={total_processed['changes']} "
            f"total_processed_notes={total_processed['notes']} "
            f"total_processed_terms={total_processed['terms']} "
            f"term_rel_note_total={after['term_note_total']} "
            f"note_total={after['note_total']} "
            f"coverage_ratio={after['coverage_ratio']:.4f} "
            f"change_log_pending={after['change_log_pending']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
