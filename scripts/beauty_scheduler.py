from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.services.beauty_catalog import sync_beauty_catalog
from app.services.brand_recognition import sync_brand_dictionary, sync_note_brand_relations
from app.services.beauty_taxonomy import BEAUTY_ALL_KEYWORDS
from scripts.crawl_xhs_beauty import crawl_keywords_for_list
from scripts.enrich_anchor_ids_from_nickname import main as enrich_anchor_ids_from_nickname
from scripts.enqueue_anchor_info_backfill import main as enqueue_anchor_info_backfill
from scripts.enqueue_fans_portrait_backfill import main as enqueue_fans_portrait_backfill
from scripts.enqueue_note_comment_backfill import main as enqueue_note_comment_backfill
from scripts.enqueue_note_info_backfill import main as enqueue_note_info_backfill

STATE_FILE = Path("/tmp/xhs_beauty_scheduler_offset.txt")


def _load_offset() -> int:
    if not STATE_FILE.exists():
        return 0
    try:
        return int(STATE_FILE.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    STATE_FILE.write_text(str(offset), encoding="utf-8")


def _select_keyword_batch(batch_size: int) -> list[str]:
    if not BEAUTY_ALL_KEYWORDS:
        return []

    safe_batch_size = max(1, min(batch_size, len(BEAUTY_ALL_KEYWORDS)))
    offset = _load_offset() % len(BEAUTY_ALL_KEYWORDS)
    batch: list[str] = []

    for index in range(safe_batch_size):
        batch.append(BEAUTY_ALL_KEYWORDS[(offset + index) % len(BEAUTY_ALL_KEYWORDS)])

    _save_offset((offset + safe_batch_size) % len(BEAUTY_ALL_KEYWORDS))
    return batch


def _parse_search_sorts(raw: str) -> list[int]:
    sorts: list[int] = []
    for part in raw.split(","):
        text = part.strip()
        if text not in {"0", "1"}:
            continue
        value = int(text)
        if value not in sorts:
            sorts.append(value)
    return sorts or [1]


def run_cycle() -> dict[str, int]:
    settings = get_settings()
    db = SessionLocal()
    try:
        catalog_result = sync_beauty_catalog(db)
        brand_seed_count = sync_brand_dictionary(db)
        brand_match_count = sync_note_brand_relations(
            db,
            min_like=0,
            recent_hours=settings.beauty_scheduler_recent_hours,
            refresh_existing=True,
        )
    finally:
        db.close()

    keyword_batch = _select_keyword_batch(settings.beauty_scheduler_keyword_batch_size)
    search_rows = 0
    search_sorts = _parse_search_sorts(settings.beauty_scheduler_search_sorts)
    for sort in search_sorts:
        search_rows += crawl_keywords_for_list(
            keyword_batch,
            limit_per_keyword=settings.beauty_scheduler_search_limit,
            sort=sort,
        )
    nickname_anchor_matches = enrich_anchor_ids_from_nickname(
        limit=settings.beauty_scheduler_nickname_anchor_limit,
        min_like=100,
        spacing_seconds=settings.beauty_scheduler_nickname_anchor_spacing_seconds,
    )
    note_info_jobs = enqueue_note_info_backfill(
        limit=settings.beauty_scheduler_note_info_limit,
        recent_hours=settings.beauty_scheduler_recent_hours,
        min_like=100,
        refresh_all=True,
        max_pending=settings.beauty_scheduler_note_info_limit,
    )
    note_comment_jobs = enqueue_note_comment_backfill(
        limit=settings.beauty_scheduler_note_comment_limit,
        recent_hours=settings.beauty_scheduler_recent_hours,
        max_pending=settings.beauty_scheduler_note_comment_limit,
    )
    anchor_jobs = enqueue_anchor_info_backfill(
        limit=settings.beauty_scheduler_anchor_limit,
        recent_hours=settings.beauty_scheduler_recent_hours,
        max_pending=settings.beauty_scheduler_anchor_limit,
    )
    fans_jobs = 0
    if settings.beauty_scheduler_fans_limit > 0:
        fans_jobs = enqueue_fans_portrait_backfill(limit=settings.beauty_scheduler_fans_limit)

    return {
        "category_count": catalog_result["category_count"],
        "beauty_keyword_count": catalog_result["keyword_count"],
        "keyword_batch_size": len(keyword_batch),
        "brand_seed_count": brand_seed_count,
        "brand_match_count": brand_match_count,
        "recent_hours": settings.beauty_scheduler_recent_hours,
        "search_sort_count": len(search_sorts),
        "search_rows": search_rows,
        "nickname_anchor_matches": nickname_anchor_matches,
        "note_info_jobs": note_info_jobs,
        "note_comment_jobs": note_comment_jobs,
        "anchor_jobs": anchor_jobs,
        "fans_jobs": fans_jobs,
    }


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    settings = get_settings()

    while True:
        started_at = _timestamp()
        print(f"[beauty-scheduler] cycle_start={started_at}")
        try:
            result = run_cycle()
            print(
                "[beauty-scheduler] cycle_done "
                f"categories={result['category_count']} "
                f"beauty_keywords={result['beauty_keyword_count']} "
                f"keyword_batch_size={result['keyword_batch_size']} "
                f"brand_seed_count={result['brand_seed_count']} "
                f"brand_match_count={result['brand_match_count']} "
                f"recent_hours={result['recent_hours']} "
                f"search_sort_count={result['search_sort_count']} "
                f"search_rows={result['search_rows']} "
                f"nickname_anchor_matches={result['nickname_anchor_matches']} "
                f"note_info_jobs={result['note_info_jobs']} "
                f"note_comment_jobs={result['note_comment_jobs']} "
                f"anchor_jobs={result['anchor_jobs']} "
                f"fans_jobs={result['fans_jobs']}"
            )
        except Exception as exc:
            print(f"[beauty-scheduler] cycle_error={exc}")

        if args.once:
            break

        sleep_seconds = max(settings.beauty_scheduler_interval_minutes, 1) * 60
        print(f"[beauty-scheduler] next_cycle_in_seconds={sleep_seconds}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
