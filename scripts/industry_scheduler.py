from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.services.brand_recognition import sync_brand_dictionary, sync_note_brand_relations
from app.services.industry_catalog import get_all_industry_keywords, sync_industry_catalog
from app.services.search_center import get_term_rel_coverage_stats, process_note_change_log
from scripts.crawl_xhs_beauty import crawl_keywords_for_list
from scripts.backfill_unclassified_industries import run_backfill_batch
from scripts.enrich_anchor_ids_from_nickname import main as enrich_anchor_ids_from_nickname
from scripts.enqueue_anchor_info_backfill import main as enqueue_anchor_info_backfill
from scripts.enqueue_fans_portrait_backfill import main as enqueue_fans_portrait_backfill
from scripts.enqueue_note_comment_backfill import main as enqueue_note_comment_backfill
from scripts.enqueue_note_info_backfill import main as enqueue_note_info_backfill

STATE_FILE = Path("/tmp/xhs_industry_scheduler_offset.txt")
RECOVER_TASK_TYPES = ("note_search", "note_info", "note_comment", "anchor_info", "fans_portrait")
_last_search_incremental_run_at: float = 0.0
_last_running_recover_at: float = 0.0


@dataclass
class AdaptiveProfile:
    mode: str
    multiplier: float
    fail_ratio: float
    rate_limited: int
    total: int


def _load_offset() -> int:
    if not STATE_FILE.exists():
        return 0
    try:
        return int(STATE_FILE.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    STATE_FILE.write_text(str(offset), encoding="utf-8")


def _parse_search_sorts(raw: str) -> list[int]:
    sorts: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if value not in {"0", "1"}:
            continue
        parsed = int(value)
        if parsed not in sorts:
            sorts.append(parsed)
    return sorts or [1]


def _scaled(base: int, multiplier: float, min_value: int = 0, max_value: int | None = None) -> int:
    value = int(math.ceil(base * multiplier))
    value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _load_keyword_pool() -> list[str]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT keyword
                FROM xhs_industry_keyword_dim
                WHERE status = 'enabled'
                  AND is_blacklist = false
                ORDER BY priority ASC, industry_key ASC, keyword ASC
                """
            )
        ).scalars().all()
        keywords = [str(item).strip() for item in rows if str(item).strip()]
    except Exception:
        keywords = []
    finally:
        db.close()

    if keywords:
        return keywords
    return get_all_industry_keywords()


def _select_keyword_batch(keyword_pool: list[str], batch_size: int) -> list[str]:
    if not keyword_pool:
        return []

    safe_batch_size = max(1, min(batch_size, len(keyword_pool)))
    offset = _load_offset() % len(keyword_pool)
    batch: list[str] = []
    for index in range(safe_batch_size):
        batch.append(keyword_pool[(offset + index) % len(keyword_pool)])
    _save_offset((offset + safe_batch_size) % len(keyword_pool))
    return batch


def _compute_adaptive_profile() -> AdaptiveProfile:
    settings = get_settings()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                    COUNT(*) FILTER (
                        WHERE
                            COALESCE(error_msg, '') ILIKE '%429%'
                            OR COALESCE(error_msg, '') ILIKE '%timeout%'
                            OR COALESCE(response_payload::text, '') ILIKE '%429%'
                            OR COALESCE(response_payload::text, '') ILIKE '%too many%'
                    ) AS rate_limited
                FROM xhs_crawl_log
                WHERE created_at >= now() - (:window_minutes || ' minute')::interval
                  AND task_type IN ('note_search', 'note_info', 'note_comment', 'anchor_info')
                """
            ),
            {"window_minutes": settings.industry_scheduler_adaptive_window_minutes},
        ).mappings().first()
    finally:
        db.close()

    total = int(row.get("total") or 0) if row else 0
    failed = int(row.get("failed") or 0) if row else 0
    rate_limited = int(row.get("rate_limited") or 0) if row else 0
    fail_ratio = (failed / total) if total > 0 else 0.0

    if (
        total > 30
        and fail_ratio >= settings.industry_scheduler_backoff_fail_ratio_threshold
        and rate_limited >= settings.industry_scheduler_backoff_rate_limit_threshold
    ):
        return AdaptiveProfile(
            mode="backoff",
            multiplier=settings.industry_scheduler_backoff_multiplier,
            fail_ratio=fail_ratio,
            rate_limited=rate_limited,
            total=total,
        )
    if (
        total > 30
        and fail_ratio <= settings.industry_scheduler_boost_fail_ratio_threshold
        and rate_limited <= settings.industry_scheduler_boost_rate_limit_threshold
    ):
        return AdaptiveProfile(
            mode="boost",
            multiplier=settings.industry_scheduler_boost_multiplier,
            fail_ratio=fail_ratio,
            rate_limited=rate_limited,
            total=total,
        )
    return AdaptiveProfile(mode="steady", multiplier=1.0, fail_ratio=fail_ratio, rate_limited=rate_limited, total=total)


def _collect_ingest_health_metrics() -> dict[str, int | float]:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*)::bigint FROM xhs_note_fact WHERE created_at >= now() - interval '1 minute') AS notes_new_1m,
                    (SELECT COUNT(*)::bigint FROM xhs_crawl_log WHERE created_at >= now() - interval '1 minute' AND status = 'success') AS crawl_success_1m,
                    (SELECT COUNT(*)::bigint FROM xhs_crawl_log WHERE created_at >= now() - interval '1 minute' AND status = 'failed') AS crawl_failed_1m,
                    (SELECT COUNT(*)::bigint FROM xhs_note_industry_rel WHERE updated_at >= now() - interval '5 minute') AS industry_rel_5m,
                    (SELECT COUNT(*)::bigint FROM xhs_note_industry_rel WHERE updated_at >= now() - interval '15 minute') AS industry_rel_15m,
                    (SELECT COUNT(*)::bigint FROM xhs_note_industry_rel WHERE updated_at >= now() - interval '60 minute') AS industry_rel_60m,
                    (SELECT COUNT(*)::bigint FROM xhs_note_fact) AS notes_total,
                    (SELECT COUNT(DISTINCT note_id)::bigint FROM xhs_note_industry_rel) AS classified_notes
                """
            )
        ).mappings().first()
    finally:
        db.close()

    notes_total = int((row or {}).get("notes_total") or 0)
    classified_notes = int((row or {}).get("classified_notes") or 0)
    unclassified_total = max(0, notes_total - classified_notes)
    classify_coverage = (classified_notes / notes_total) if notes_total > 0 else 0.0

    return {
        "notes_new_1m": int((row or {}).get("notes_new_1m") or 0),
        "crawl_success_1m": int((row or {}).get("crawl_success_1m") or 0),
        "crawl_failed_1m": int((row or {}).get("crawl_failed_1m") or 0),
        "industry_rel_5m": int((row or {}).get("industry_rel_5m") or 0),
        "industry_rel_15m": int((row or {}).get("industry_rel_15m") or 0),
        "industry_rel_60m": int((row or {}).get("industry_rel_60m") or 0),
        "notes_total": notes_total,
        "classified_notes": classified_notes,
        "unclassified_total": unclassified_total,
        "classify_coverage": round(classify_coverage, 4),
    }


def _recent_comment_limit_errors(window_minutes: int = 20) -> int:
    db = SessionLocal()
    try:
        value = db.execute(
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
            {"window_minutes": max(5, window_minutes)},
        ).scalar()
        return int(value or 0)
    finally:
        db.close()


def _recover_stale_running_tasks(timeout_minutes: int) -> int:
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET status = 'failed_timeout',
                    error_msg = COALESCE(NULLIF(error_msg, ''), 'timeout auto-recovered by scheduler'),
                    completed_at = COALESCE(completed_at, now()),
                    updated_at = now()
                WHERE status = 'running'
                  AND COALESCE(is_callback_received, false) = false
                  AND task_type = ANY(CAST(:task_types AS text[]))
                  AND created_at < now() - ((:timeout_minutes)::text || ' minute')::interval
                """
            ),
            {"task_types": list(RECOVER_TASK_TYPES), "timeout_minutes": max(10, int(timeout_minutes))},
        )
        recovered = int(result.rowcount or 0)
        if recovered > 0:
            db.commit()
        else:
            db.rollback()
        return recovered
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()


def _run_search_incremental_cycle() -> dict[str, int | float]:
    settings = get_settings()
    db = SessionLocal()
    try:
        pending_before = int(
            db.execute(
                text("SELECT COUNT(*) FROM xhs_note_change_log WHERE processed_at IS NULL")
            ).scalar()
            or 0
        )
        timeout_ms = max(1000, int(getattr(settings, "search_incremental_worker_timeout_ms", 12000)))
        db.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        result = process_note_change_log(
            db,
            batch_size=max(1, int(getattr(settings, "search_incremental_batch_size", 3000))),
        )
        coverage = get_term_rel_coverage_stats(db)
        if int(result.get("changes") or 0) > 0:
            db.commit()
        else:
            db.rollback()
        return {
            "search_incremental_changes": int(result.get("changes") or 0),
            "search_incremental_notes": int(result.get("notes") or 0),
            "search_incremental_authors": int(result.get("authors") or 0),
            "search_incremental_terms": int(result.get("terms") or 0),
            "search_incremental_backlog": pending_before,
            "search_incremental_backlog_warn": int(
                pending_before >= max(1, int(getattr(settings, "search_incremental_backlog_warn_threshold", 10000)))
            ),
            "term_rel_note_total": int(coverage.get("term_note_total") or 0),
            "term_rel_note_coverage": float(coverage.get("coverage_ratio") or 0.0),
        }
    except Exception:
        db.rollback()
        return {
            "search_incremental_changes": 0,
            "search_incremental_notes": 0,
            "search_incremental_authors": 0,
            "search_incremental_terms": 0,
            "search_incremental_backlog": 0,
            "search_incremental_backlog_warn": 0,
            "term_rel_note_total": 0,
            "term_rel_note_coverage": 0.0,
        }
    finally:
        db.close()


def run_cycle() -> dict[str, int | str | float]:
    global _last_search_incremental_run_at, _last_running_recover_at
    settings = get_settings()
    now_monotonic = time.monotonic()
    adaptive = _compute_adaptive_profile()
    recovered_running_timeout = 0
    recover_interval = max(60, int(getattr(settings, "search_running_recover_interval_seconds", 300)))
    if now_monotonic - _last_running_recover_at >= recover_interval:
        recovered_running_timeout = _recover_stale_running_tasks(
            timeout_minutes=int(getattr(settings, "crawl_running_timeout_minutes", 90))
        )
        _last_running_recover_at = now_monotonic
    incremental = {
        "search_incremental_changes": 0,
        "search_incremental_notes": 0,
        "search_incremental_authors": 0,
        "search_incremental_terms": 0,
        "search_incremental_backlog": 0,
        "search_incremental_backlog_warn": 0,
        "term_rel_note_total": 0,
        "term_rel_note_coverage": 0.0,
    }
    incremental_interval = max(30, int(getattr(settings, "search_incremental_refresh_interval_seconds", 60)))
    if now_monotonic - _last_search_incremental_run_at >= incremental_interval:
        incremental = _run_search_incremental_cycle()
        _last_search_incremental_run_at = now_monotonic

    db = SessionLocal()
    try:
        catalog_result = sync_industry_catalog(db)
        brand_seed_count = sync_brand_dictionary(db)
        brand_match_count = sync_note_brand_relations(
            db,
            limit=5000,
            min_like=0,
            recent_hours=settings.industry_scheduler_recent_hours,
            refresh_existing=True,
        )
    finally:
        db.close()

    keyword_pool = _load_keyword_pool()
    dynamic_keyword_batch_size = _scaled(
        settings.industry_scheduler_keyword_batch_size,
        adaptive.multiplier,
        min_value=12,
        max_value=len(keyword_pool) if keyword_pool else None,
    )
    keyword_batch = _select_keyword_batch(keyword_pool, dynamic_keyword_batch_size)
    dynamic_search_limit = _scaled(settings.industry_scheduler_search_limit, adaptive.multiplier, min_value=60)

    search_sorts = _parse_search_sorts(settings.industry_scheduler_search_sorts)
    search_rows = 0
    for sort in search_sorts:
        search_rows += crawl_keywords_for_list(
            keyword_batch,
            limit_per_keyword=dynamic_search_limit,
            sort=sort,
            biz_type="industry_keyword_crawl",
        )

    spacing_scale = max(0.4, 1 / max(adaptive.multiplier, 0.2))
    note_info_limit = _scaled(settings.industry_scheduler_note_info_limit, adaptive.multiplier, min_value=0)
    note_comment_limit = _scaled(settings.industry_scheduler_note_comment_limit, adaptive.multiplier, min_value=0)
    anchor_limit = _scaled(settings.industry_scheduler_anchor_limit, adaptive.multiplier, min_value=0)
    fans_limit = _scaled(settings.industry_scheduler_fans_limit, adaptive.multiplier, min_value=0)
    nickname_anchor_limit = _scaled(settings.industry_scheduler_nickname_anchor_limit, adaptive.multiplier, min_value=0)
    comment_limit_errors = _recent_comment_limit_errors()
    comment_protection_mode = comment_limit_errors >= 60
    if comment_protection_mode:
        # Provider task pool is saturated: pause comment enqueue and reduce heavy inflow.
        note_info_limit = min(note_info_limit, 220)
        anchor_limit = min(anchor_limit, 60)
        fans_limit = min(fans_limit, 20)
        note_comment_limit = 0

    nickname_anchor_matches = enrich_anchor_ids_from_nickname(
        limit=nickname_anchor_limit,
        min_like=100,
        spacing_seconds=max(0.5, settings.industry_scheduler_nickname_anchor_spacing_seconds * spacing_scale),
    )
    note_info_jobs = enqueue_note_info_backfill(
        limit=note_info_limit,
        recent_hours=settings.industry_scheduler_recent_hours,
        min_like=0,
        min_interaction=0,
        refresh_all=True,
        max_pending=max(note_info_limit * 80, 20000),
        spacing_seconds=max(1, int(math.ceil(settings.huitun_auto_note_info_spacing_seconds * spacing_scale))),
    )
    note_comment_jobs = enqueue_note_comment_backfill(
        limit=note_comment_limit,
        recent_hours=settings.industry_scheduler_recent_hours,
        min_like=20,
        min_interaction=60,
        max_pending=max(note_comment_limit * 20, 2500),
        spacing_seconds=max(
            12 if comment_protection_mode else 2,
            int(math.ceil(settings.huitun_auto_note_comment_spacing_seconds * spacing_scale)),
        ),
    )
    anchor_jobs = enqueue_anchor_info_backfill(
        limit=anchor_limit,
        recent_hours=settings.industry_scheduler_recent_hours,
        max_pending=max(anchor_limit * 80, 15000),
        spacing_seconds=max(6, int(math.ceil(12 * spacing_scale))),
    )
    fans_jobs = 0
    if fans_limit > 0:
        fans_jobs = enqueue_fans_portrait_backfill(limit=fans_limit)

    backfill_result = run_backfill_batch(
        limit=settings.industry_classify_backfill_batch_size,
        shards=max(1, settings.industry_classify_backfill_shards),
        shard_index=max(0, settings.industry_classify_backfill_shard_index),
        namespace="scheduler",
        reset_cursor=False,
    )
    health = _collect_ingest_health_metrics()

    return {
        "industry_count": catalog_result["industry_count"],
        "industry_keyword_count": catalog_result["keyword_count"],
        "brand_seed_count": brand_seed_count,
        "brand_match_count": brand_match_count,
        "adaptive_mode": adaptive.mode,
        "adaptive_multiplier": round(adaptive.multiplier, 3),
        "adaptive_fail_ratio": round(adaptive.fail_ratio, 4),
        "adaptive_rate_limited": adaptive.rate_limited,
        "adaptive_total": adaptive.total,
        "keyword_pool_size": len(keyword_pool),
        "keyword_batch_size": len(keyword_batch),
        "search_sort_count": len(search_sorts),
        "search_limit": dynamic_search_limit,
        "search_rows": search_rows,
        "nickname_anchor_matches": nickname_anchor_matches,
        "note_info_jobs": note_info_jobs,
        "note_comment_jobs": note_comment_jobs,
        "comment_limit_errors_20m": comment_limit_errors,
        "comment_protection_mode": int(comment_protection_mode),
        "recovered_running_timeout": recovered_running_timeout,
        "search_incremental_changes": int(incremental["search_incremental_changes"]),
        "search_incremental_notes": int(incremental["search_incremental_notes"]),
        "search_incremental_authors": int(incremental["search_incremental_authors"]),
        "search_incremental_terms": int(incremental["search_incremental_terms"]),
        "search_incremental_backlog": int(incremental["search_incremental_backlog"]),
        "search_incremental_backlog_warn": int(incremental["search_incremental_backlog_warn"]),
        "term_rel_note_total": int(incremental["term_rel_note_total"]),
        "term_rel_note_coverage": float(incremental["term_rel_note_coverage"]),
        "anchor_jobs": anchor_jobs,
        "fans_jobs": fans_jobs,
        "backfill_scanned": int(backfill_result.get("scanned") or 0),
        "backfill_matched": int(backfill_result.get("matched") or 0),
        "notes_new_1m": int(health["notes_new_1m"]),
        "crawl_success_1m": int(health["crawl_success_1m"]),
        "crawl_failed_1m": int(health["crawl_failed_1m"]),
        "industry_rel_5m": int(health["industry_rel_5m"]),
        "industry_rel_15m": int(health["industry_rel_15m"]),
        "industry_rel_60m": int(health["industry_rel_60m"]),
        "notes_total": int(health["notes_total"]),
        "classified_notes": int(health["classified_notes"]),
        "unclassified_total": int(health["unclassified_total"]),
        "classify_coverage": float(health["classify_coverage"]),
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
        print(f"[industry-scheduler] cycle_start={started_at}")
        try:
            result = run_cycle()
            print(
                "[industry-scheduler] cycle_done "
                f"industries={result['industry_count']} "
                f"industry_keywords={result['industry_keyword_count']} "
                f"brand_seed_count={result['brand_seed_count']} "
                f"brand_match_count={result['brand_match_count']} "
                f"adaptive_mode={result['adaptive_mode']} "
                f"adaptive_multiplier={result['adaptive_multiplier']} "
                f"adaptive_fail_ratio={result['adaptive_fail_ratio']} "
                f"adaptive_rate_limited={result['adaptive_rate_limited']} "
                f"adaptive_total={result['adaptive_total']} "
                f"keyword_pool_size={result['keyword_pool_size']} "
                f"keyword_batch_size={result['keyword_batch_size']} "
                f"search_sort_count={result['search_sort_count']} "
                f"search_limit={result['search_limit']} "
                f"search_rows={result['search_rows']} "
                f"nickname_anchor_matches={result['nickname_anchor_matches']} "
                f"note_info_jobs={result['note_info_jobs']} "
                f"note_comment_jobs={result['note_comment_jobs']} "
                f"recovered_running_timeout={result['recovered_running_timeout']} "
                f"search_incremental_changes={result['search_incremental_changes']} "
                f"search_incremental_notes={result['search_incremental_notes']} "
                f"search_incremental_authors={result['search_incremental_authors']} "
                f"search_incremental_terms={result['search_incremental_terms']} "
                f"search_incremental_backlog={result['search_incremental_backlog']} "
                f"search_incremental_backlog_warn={result['search_incremental_backlog_warn']} "
                f"term_rel_note_total={result['term_rel_note_total']} "
                f"term_rel_note_coverage={result['term_rel_note_coverage']:.4f} "
                f"anchor_jobs={result['anchor_jobs']} "
                f"fans_jobs={result['fans_jobs']} "
                f"backfill_scanned={result['backfill_scanned']} "
                f"backfill_matched={result['backfill_matched']} "
                f"notes_new_1m={result['notes_new_1m']} "
                f"crawl_success_1m={result['crawl_success_1m']} "
                f"crawl_failed_1m={result['crawl_failed_1m']} "
                f"industry_rel_5m={result['industry_rel_5m']} "
                f"industry_rel_15m={result['industry_rel_15m']} "
                f"industry_rel_60m={result['industry_rel_60m']} "
                f"notes_total={result['notes_total']} "
                f"classified_notes={result['classified_notes']} "
                f"unclassified_total={result['unclassified_total']} "
                f"classify_coverage={result['classify_coverage']}"
            )
        except Exception as exc:
            print(f"[industry-scheduler] cycle_error={exc}")

        if args.once:
            break

        sleep_seconds = max(settings.industry_scheduler_interval_minutes, 1) * 60
        print(f"[industry-scheduler] next_cycle_in_seconds={sleep_seconds}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
