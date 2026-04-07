from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import (
    APIResponse,
    BrandCategorySearchRequest,
    InfluencerSearchRequest,
    SearchCategoryRequest,
)
from app.services.search_center import (
    build_fetch_decision,
    create_search_job,
    get_search_job,
    mark_search_job_failed,
    mark_search_job_running,
    query_brand_category_db_first,
    query_brand_category_db_first_v2,
    query_influencers_db_first,
    query_influencers_db_first_v2,
    try_sync_job_status_with_crawl,
)
from app.services.ingest import create_crawl_log
from app.services.industry_catalog import resolve_industry_key
from app.tasks.jobs import run_search_anchors, run_search_notes, trigger_anchor_info, trigger_fans_portrait

router = APIRouter(prefix="/search", tags=["search"])
settings = get_settings()
logger = logging.getLogger(__name__)

_redis_client: Redis | None = None
_last_stale_recover_at: datetime | None = None
_RECOVER_TASK_TYPES = ("note_search", "note_info", "note_comment", "anchor_info", "fans_portrait")


def _sort_label(sort: int) -> str:
    return "read_desc" if sort == 1 else "publish_desc"


def _normalize_note_rows(rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        if item.get("publish_time"):
            item["publish_time"] = item["publish_time"].isoformat()
        item["tags"] = item.get("tags") or []
        items.append(item)
    return items


def _get_latest_cached_batch(
    db: Session,
    *,
    keyword: str,
    sort_type: str,
    freshness_hours: int,
) -> str | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
    row = db.execute(
        text(
            """
            SELECT batch_id, MAX(created_at) AS latest_at
            FROM xhs_note_search_result
            WHERE keyword = :keyword
              AND sort_type = :sort_type
              AND created_at >= :cutoff
            GROUP BY batch_id
            ORDER BY latest_at DESC
            LIMIT 1
            """
        ),
        {"keyword": keyword, "sort_type": sort_type, "cutoff": cutoff},
    ).mappings().first()
    return str(row["batch_id"]) if row else None


def _get_search_result_page(
    db: Session,
    *,
    batch_id: str,
    page: int,
    size: int,
) -> dict:
    offset = (page - 1) * size

    total = db.execute(
        text("SELECT COUNT(*) FROM xhs_note_search_result WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).scalar_one()

    rows = db.execute(
        text(
            """
            SELECT
                nsr.note_id,
                COALESCE(nf.title, nsr.title) AS title,
                nf.author_id,
                COALESCE(nf.author_nickname, nsr.author_nickname) AS author_nickname,
                COALESCE(nf.read_count, 0) AS read_count,
                COALESCE(nf.like_count, 0) AS like_count,
                COALESCE(nf.comment_count, 0) AS comment_count,
                COALESCE(nf.collection_count, 0) AS collection_count,
                COALESCE(nf.share_count, 0) AS share_count,
                'https://www.xiaohongshu.com/explore/' || nsr.note_id AS post_url,
                COALESCE(nf.publish_time, nsr.publish_time) AS publish_time,
                COALESCE(nf.tags, ARRAY[]::text[]) AS tags,
                nsr.search_rank
            FROM xhs_note_search_result nsr
            LEFT JOIN xhs_note_fact nf
              ON nf.note_id = nsr.note_id
            WHERE nsr.batch_id = :batch_id
            ORDER BY nsr.search_rank ASC
            LIMIT :size OFFSET :offset
            """
        ),
        {"batch_id": batch_id, "size": size, "offset": offset},
    ).mappings().all()

    items = _normalize_note_rows([dict(r) for r in rows])

    return {
        "list": items,
        "pagination": {
            "total": total,
            "page": page,
            "size": size,
            "has_more": offset + len(items) < total,
            "total_is_estimate": False,
        },
    }


def _safe_payload(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text_value = str(raw).strip()
    if not text_value:
        return None
    if text_value.endswith("Z"):
        text_value = f"{text_value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _freshness_seconds(result: dict) -> int | None:
    freshness = _parse_iso_datetime(str(result.get("freshness") or ""))
    if not freshness:
        return None
    age_seconds = int((datetime.now(timezone.utc) - freshness).total_seconds())
    return max(0, age_seconds)


def _add_result_meta(result: dict, *, health: dict, pending: bool, pending_reason: str | None = None) -> dict:
    payload = dict(result)
    payload["health"] = health
    payload["data_freshness_seconds"] = _freshness_seconds(result)
    if pending or pending_reason:
        payload["pending_reason"] = pending_reason or ("|".join(health.get("reasons") or []) or "refreshing")
    if pending:
        payload["next_poll_after_ms"] = max(1000, int(settings.search_pending_poll_ms))
    return payload


def _result_total(result: dict | None) -> int:
    if not isinstance(result, dict):
        return 0
    pagination = result.get("pagination")
    if not isinstance(pagination, dict):
        return 0
    try:
        return max(0, int(pagination.get("total") or 0))
    except Exception:
        return 0


def _result_hit(result: dict | None) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(result.get("hit"))


def _result_has_more(result: dict | None) -> bool:
    if not isinstance(result, dict):
        return False
    pagination = result.get("pagination")
    if not isinstance(pagination, dict):
        return False
    return bool(pagination.get("has_more"))


def _result_items_count(result: dict | None) -> int:
    if not isinstance(result, dict):
        return 0
    items = result.get("items")
    if not isinstance(items, list):
        return 0
    return len(items)


def _should_schedule_background_backfill(
    result: dict | None,
    *,
    force_refresh: bool,
    page_size: int,
    min_results: int = 30,
) -> tuple[bool, dict]:
    should_backfill, health = _needs_backfill(
        result or {},
        force_refresh=force_refresh,
        min_results=max(1, int(min_results)),
    )
    visible_items = _result_items_count(result)
    if visible_items < max(1, int(page_size)):
        should_backfill = True
        reasons = list(health.get("reasons") or [])
        if "page_underfilled" not in reasons:
            reasons.append("page_underfilled")
        health["reasons"] = reasons
        health["healthy"] = False
    return should_backfill, health


def _should_keep_pending_until_first_page_full(result: dict | None, *, page_size: int) -> bool:
    if not isinstance(result, dict):
        return True
    if not _result_hit(result):
        return True
    visible_items = _result_items_count(result)
    if visible_items > 0:
        return False
    return True


def _should_run_v2_recall_guard(
    *,
    query: str,
    v2_result: dict | None,
    page_size: int | None = None,
    page: int | None = None,
) -> bool:
    if not settings.search_v2_recall_guard_enabled:
        return False
    if not query.strip():
        return False
    if not isinstance(v2_result, dict):
        return False
    if not _result_hit(v2_result):
        return True

    total = _result_total(v2_result)
    min_total = max(1, int(settings.search_v2_recall_guard_min_total))
    if total < min_total:
        return True

    if page_size is not None and int(page_size) > 0:
        # Guard against under-recall plateaus: exactly one page returned and no
        # more pages, while legacy may still have much larger coverage.
        if total <= int(page_size) and not _result_has_more(v2_result):
            return True
        # Guard deep-page empties where v2 estimated totals stop early and user
        # lands on an empty page despite non-empty prior pages.
        if int(page or 1) > 1 and _result_items_count(v2_result) == 0 and total > 0:
            return True

    return False


def _should_prefer_legacy_for_recall_guard(*, v2_result: dict | None, legacy_result: dict | None) -> bool:
    if not isinstance(v2_result, dict) or not isinstance(legacy_result, dict):
        return False
    delta = max(0, int(settings.search_v2_recall_guard_delta))
    return _result_total(legacy_result) >= (_result_total(v2_result) + delta)


def _get_redis_client() -> Redis | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = Redis.from_url(settings.celery_broker_url, decode_responses=True, socket_timeout=1)
        _redis_client.ping()
    except Exception:
        _redis_client = None
    return _redis_client


def _coalesce_cache_key(*, search_type: str, query: str, mode: str | None, industry: str | None, date_range: int) -> str:
    payload = f"{search_type}|{query.strip().lower()}|{(mode or '').lower()}|{(resolve_industry_key(industry) or '').lower()}|{int(date_range)}"
    digest = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"xhs:search:coalesce:{digest}"


def _result_cache_key(search_type: str, payload: dict) -> str:
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()
    return f"xhs:search:result:{search_type}:{digest}"


def _read_result_cache(cache_key: str) -> dict | None:
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    try:
        raw = redis_client.get(cache_key)
    except RedisError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _write_result_cache(cache_key: str, payload: dict, ttl_seconds: int) -> None:
    redis_client = _get_redis_client()
    if not redis_client:
        return
    try:
        def _json_default(value):
            if isinstance(value, Decimal):
                try:
                    if value == value.to_integral_value():
                        return int(value)
                except Exception:
                    pass
                return float(value)
            return str(value)

        redis_client.set(
            cache_key,
            json.dumps(payload, ensure_ascii=False, default=_json_default),
            ex=max(10, ttl_seconds),
        )
    except RedisError:
        return


def _load_active_job(db: Session, job_id: str | None) -> dict | None:
    if not job_id:
        return None
    job = try_sync_job_status_with_crawl(db, job_id=job_id) or get_search_job(db, job_id)
    if not job:
        return None
    if str(job.get("status") or "") not in {"pending", "running"}:
        return None
    return job


def _try_reuse_coalesced_job(db: Session, *, cache_key: str, wait_ms: int) -> dict | None:
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    try:
        cached_job_id = redis_client.get(cache_key)
    except RedisError:
        return None
    active = _load_active_job(db, cached_job_id)
    if active:
        return active

    deadline = time.monotonic() + max(wait_ms, 0) / 1000
    while time.monotonic() < deadline:
        time.sleep(0.15)
        try:
            cached_job_id = redis_client.get(cache_key)
        except RedisError:
            return None
        active = _load_active_job(db, cached_job_id)
        if active:
            return active
    return None


def _schedule_influencer_backfill_job(
    db: Session,
    *,
    query: str,
    industry: str | None,
    date_range: int,
    request_payload: dict,
    wait_ms_if_locked: int,
) -> dict | None:
    cache_key = _coalesce_cache_key(
        search_type="influencer",
        query=query,
        mode=None,
        industry=industry,
        date_range=date_range,
    )
    lock_key = f"{cache_key}:lock"
    redis_client = _get_redis_client()

    reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=0)
    if reused_job:
        return reused_job

    lock_token = uuid.uuid4().hex
    lock_acquired = True
    if redis_client:
        try:
            lock_acquired = bool(
                redis_client.set(lock_key, lock_token, nx=True, ex=settings.search_coalesce_lock_ttl_seconds)
            )
        except RedisError:
            lock_acquired = True

    if not lock_acquired:
        reused_job = _try_reuse_coalesced_job(
            db,
            cache_key=cache_key,
            wait_ms=max(0, int(wait_ms_if_locked)),
        )
        if reused_job:
            return reused_job
        return None

    try:
        if query and _has_recent_zero_result_note_search_task(
            db,
            keyword=query,
            minutes=5,
        ):
            return None
        job_id = create_search_job(
            db,
            search_type="influencer",
            query=query,
            mode=None,
            industry=industry,
            request_payload=request_payload,
        )
        batch_id = uuid.uuid4().hex[:16]
        trigger_task = run_search_notes.apply_async(
            kwargs={
                "batch_id": batch_id,
                "keyword": query or str(industry or "小红书"),
                "sort": 1,
                "max_items": 240,
                "auto_enrich": True,
                "trigger_comments": False,
            },
            queue=settings.task_priority_queue,
        )
        run_search_anchors.apply_async(
            kwargs={
                "keyword": query or str(industry or "小红书"),
                "max_items": 120,
                "auto_enrich": True,
            },
            queue=settings.task_priority_queue,
        )
        mark_search_job_running(
            db,
            job_id=job_id,
            crawl_batch_id=batch_id,
            task_id=trigger_task.id,
        )
        if redis_client:
            try:
                redis_client.set(cache_key, job_id, ex=settings.search_coalesce_job_ttl_seconds)
            except RedisError:
                pass
        return {"job_id": job_id, "task_id": trigger_task.id}
    finally:
        if redis_client and lock_acquired:
            try:
                current = redis_client.get(lock_key)
                if current == lock_token:
                    redis_client.delete(lock_key)
            except RedisError:
                pass


def _schedule_brand_category_backfill_job(
    db: Session,
    *,
    query: str,
    mode: str,
    industry: str | None,
    date_range: int,
    request_payload: dict,
    wait_ms_if_locked: int,
) -> dict | None:
    cache_key = _coalesce_cache_key(
        search_type="brand_category",
        query=query,
        mode=mode,
        industry=industry,
        date_range=date_range,
    )
    lock_key = f"{cache_key}:lock"
    redis_client = _get_redis_client()

    reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=0)
    if reused_job:
        return reused_job

    lock_token = uuid.uuid4().hex
    lock_acquired = True
    if redis_client:
        try:
            lock_acquired = bool(
                redis_client.set(lock_key, lock_token, nx=True, ex=settings.search_coalesce_lock_ttl_seconds)
            )
        except RedisError:
            lock_acquired = True

    if not lock_acquired:
        reused_job = _try_reuse_coalesced_job(
            db,
            cache_key=cache_key,
            wait_ms=max(0, int(wait_ms_if_locked)),
        )
        if reused_job:
            return reused_job
        return None

    try:
        if query and _has_recent_zero_result_note_search_task(
            db,
            keyword=query,
            minutes=5,
        ):
            return None
        job_id = create_search_job(
            db,
            search_type="brand_category",
            query=query,
            mode=mode,
            industry=industry,
            request_payload=request_payload,
        )
        batch_id = uuid.uuid4().hex[:16]
        trigger_task = run_search_notes.apply_async(
            kwargs={
                "batch_id": batch_id,
                "keyword": query,
                "sort": 1,
                "max_items": 260,
                "auto_enrich": True,
                "trigger_comments": False,
            },
            queue=settings.task_priority_queue,
        )
        mark_search_job_running(
            db,
            job_id=job_id,
            crawl_batch_id=batch_id,
            task_id=trigger_task.id,
        )
        if redis_client:
            try:
                redis_client.set(cache_key, job_id, ex=settings.search_coalesce_job_ttl_seconds)
            except RedisError:
                pass
        return {"job_id": job_id, "task_id": trigger_task.id}
    finally:
        if redis_client and lock_acquired:
            try:
                current = redis_client.get(lock_key)
                if current == lock_token:
                    redis_client.delete(lock_key)
            except RedisError:
                pass


def _safe_schedule_backfill(
    schedule_fn,
    db: Session,
    *,
    context: str,
    **kwargs,
):
    try:
        return schedule_fn(db=db, **kwargs)
    except Exception as exc:
        db.rollback()
        logger.warning("search backfill schedule failed: %s (%s)", context, exc)
        return None


def _needs_backfill(
    result: dict,
    *,
    force_refresh: bool,
    min_results: int | None = None,
    stale_hours: int | None = None,
) -> tuple[bool, dict]:
    effective_stale_hours: float | None = float(stale_hours) if stale_hours is not None else None
    if effective_stale_hours is None:
        # Keep compatibility with historical SEARCH_STALE_HOURS, but prefer minute-level control.
        stale_minutes = max(1, int(getattr(settings, "search_stale_minutes", 30)))
        effective_stale_hours = max(1 / 60, stale_minutes / 60)
    decision = build_fetch_decision(
        result,
        force_refresh=force_refresh,
        min_results=min_results if min_results is not None else settings.search_min_healthy_results,
        stale_hours=effective_stale_hours,
    )
    health = dict(decision["health"])
    health["reasons"] = decision["reasons"]
    return bool(decision["need_fetch"]), health


def _should_use_brand_mode(db: Session, *, query: str, requested_mode: str, industry: str | None) -> bool:
    normalized_query = query.strip()
    if requested_mode != "category" or not normalized_query or industry:
        return requested_mode == "brand"
    # Brand-like pattern fallback: uppercase acronyms / alphanumeric tokens (YSL, K18, SK-II).
    if re.search(r"[A-Z0-9]", normalized_query):
        return True
    row = db.execute(
        text(
            """
            SELECT 1
            FROM xhs_brand_alias_dim
            WHERE COALESCE(status, 'enabled') = 'enabled'
              AND (
                    lower(alias) = lower(:query)
                 OR lower(brand_name) = lower(:query)
              )
            LIMIT 1
            """
        ),
        {"query": normalized_query},
    ).first()
    return row is not None


def _recover_stale_running_collect_tasks(db: Session) -> int:
    global _last_stale_recover_at
    now_utc = datetime.now(timezone.utc)
    if _last_stale_recover_at and (now_utc - _last_stale_recover_at).total_seconds() < 300:
        return 0
    _last_stale_recover_at = now_utc

    timeout_minutes = max(10, int(getattr(settings, "crawl_running_timeout_minutes", 90)))
    try:
        result = db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET status = 'failed_timeout',
                    error_msg = COALESCE(NULLIF(error_msg, ''), 'timeout auto-recovered'),
                    completed_at = COALESCE(completed_at, now()),
                    updated_at = now()
                WHERE status = 'running'
                  AND COALESCE(is_callback_received, false) = false
                  AND task_type = ANY(CAST(:task_types AS text[]))
                  AND created_at < now() - ((:timeout_minutes)::text || ' minute')::interval
                """
            ),
            {"task_types": list(_RECOVER_TASK_TYPES), "timeout_minutes": timeout_minutes},
        )
        updated = int(result.rowcount or 0)
        if updated > 0:
            db.commit()
        return updated
    except Exception:
        db.rollback()
        return 0


def _has_recent_collect_task(
    db: Session,
    *,
    task_type: str,
    author_id: str,
    hours: int,
) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM xhs_crawl_log
            WHERE task_type = :task_type
              AND author_id = :author_id
              AND status IN ('running', 'success')
              AND created_at >= now() - (:hours || ' hour')::interval
            LIMIT 1
            """
        ),
        {"task_type": task_type, "author_id": author_id, "hours": max(1, hours)},
    ).first()
    return row is not None


def _has_recent_note_search_task(
    db: Session,
    *,
    keyword: str,
    hours: int,
) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM xhs_crawl_log
            WHERE task_type = 'note_search'
              AND lower(keyword) = lower(:keyword)
              AND status IN ('running', 'success')
              AND created_at >= now() - (:hours || ' hour')::interval
            LIMIT 1
            """
        ),
        {"keyword": keyword, "hours": max(1, hours)},
    ).first()
    return row is not None


def _has_recent_zero_result_note_search_task(
    db: Session,
    *,
    keyword: str,
    minutes: int,
) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM xhs_crawl_log
            WHERE task_type = 'note_search'
              AND lower(keyword) = lower(:keyword)
              AND status = 'success'
              AND COALESCE(row_count, 0) = 0
              AND created_at >= now() - (:minutes || ' minute')::interval
            LIMIT 1
            """
        ),
        {"keyword": keyword, "minutes": max(1, minutes)},
    ).first()
    return row is not None


def _enqueue_creator_profile_backfill(db: Session, items: list[dict]) -> None:
    if not items:
        return

    cooldown_hours = max(1, int(getattr(settings, "search_author_backfill_cooldown_hours", 12)))
    limit = max(1, int(getattr(settings, "search_author_backfill_limit", 30)))

    seen: set[str] = set()
    candidates: list[str] = []
    for item in items[:limit]:
        author_id = str(item.get("author_id") or "").strip()
        followers = int(item.get("followers") or 0)
        if not author_id or followers > 0:
            continue
        if author_id in seen:
            continue
        seen.add(author_id)
        candidates.append(author_id)

    if not candidates:
        return

    for author_id in candidates:
        try:
            if not _has_recent_collect_task(
                db,
                task_type="anchor_info",
                author_id=author_id,
                hours=cooldown_hours,
            ):
                trigger_anchor_info.apply_async(args=[author_id], queue=settings.task_priority_queue)

            anchor_link = db.execute(
                text(
                    """
                    SELECT anchor_link
                    FROM xhs_anchor_dim
                    WHERE author_id = :author_id
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ),
                {"author_id": author_id},
            ).scalar()
            if anchor_link and not _has_recent_collect_task(
                db,
                task_type="fans_portrait",
                author_id=author_id,
                hours=cooldown_hours,
            ):
                trigger_fans_portrait.apply_async(args=[author_id], queue=settings.task_priority_queue)
        except Exception:
            # Non-blocking best effort.
            continue


def _enqueue_creator_note_backfill(db: Session, items: list[dict]) -> None:
    if not items:
        return

    cooldown_hours = max(1, int(getattr(settings, "search_creator_note_backfill_cooldown_hours", 12)))
    limit = max(1, int(getattr(settings, "search_creator_note_backfill_limit", 8)))
    threshold = max(0, int(getattr(settings, "search_creator_note_backfill_note_count_threshold", 2)))
    max_items = max(20, int(getattr(settings, "search_creator_note_backfill_max_items", 120)))

    candidates: list[str] = []
    seen_keywords: set[str] = set()
    for item in items:
        note_count = int(item.get("note_count") or 0)
        if note_count > threshold:
            continue

        nickname = str(item.get("author_nickname") or "").strip()
        if not nickname:
            continue

        marker = nickname.casefold()
        if marker in seen_keywords:
            continue
        seen_keywords.add(marker)
        candidates.append(nickname)
        if len(candidates) >= limit:
            break

    if not candidates:
        return

    for index, keyword in enumerate(candidates):
        try:
            if _has_recent_note_search_task(db, keyword=keyword, hours=cooldown_hours):
                continue
            run_search_notes.apply_async(
                kwargs={
                    "batch_id": uuid.uuid4().hex[:16],
                    "keyword": keyword,
                    "sort": 1,
                    "auto_enrich": True,
                    "trigger_comments": False,
                    "max_items": max_items,
                },
                queue=settings.task_priority_queue,
                countdown=index * 2,
            )
        except Exception:
            # Non-blocking best effort.
            continue


@router.post("/category", response_model=APIResponse)
def search_category(req: SearchCategoryRequest, db: Session = Depends(get_db)) -> APIResponse:
    keyword = req.category.strip()
    sort_type = _sort_label(req.sort)

    if not req.force_refresh:
        latest_batch_id = _get_latest_cached_batch(
            db,
            keyword=keyword,
            sort_type=sort_type,
            freshness_hours=req.freshness_hours,
        )
        if latest_batch_id:
            page_data = _get_search_result_page(
                db,
                batch_id=latest_batch_id,
                page=req.page,
                size=req.size,
            )
            return APIResponse(
                data={
                    "mode": "cache",
                    "status": "success",
                    "batch_id": latest_batch_id,
                    "keyword": keyword,
                    **page_data,
                }
            )

    batch_id = uuid.uuid4().hex[:16]
    create_crawl_log(
        db,
        batch_id=batch_id,
        task_type="note_search",
        biz_type="query",
        status="queued",
        keyword=keyword,
        request_payload={
            "keyword": keyword,
            "sort": req.sort,
            "auto_enrich": req.auto_enrich,
            "trigger_comments": req.trigger_comments,
            "max_items": req.max_items,
            "force_refresh": req.force_refresh,
            "freshness_hours": req.freshness_hours,
        },
        response_payload={"message": "queued from api"},
    )
    db.commit()

    task = run_search_notes.delay(
        batch_id=batch_id,
        keyword=keyword,
        sort=req.sort,
        auto_enrich=req.auto_enrich,
        trigger_comments=req.trigger_comments,
        max_items=req.max_items,
    )

    create_crawl_log(
        db,
        batch_id=batch_id,
        task_type="note_search",
        biz_type="query",
        status="queued",
        keyword=keyword,
        task_id=task.id,
        request_payload={
            "keyword": keyword,
            "sort": req.sort,
            "auto_enrich": req.auto_enrich,
            "trigger_comments": req.trigger_comments,
            "max_items": req.max_items,
            "force_refresh": req.force_refresh,
            "freshness_hours": req.freshness_hours,
        },
        response_payload={"message": "queued from api", "celery_task_id": task.id},
    )
    db.commit()

    return APIResponse(
        data={
            "mode": "async",
            "status": "queued",
            "batch_id": batch_id,
            "task_id": task.id,
            "keyword": keyword,
            "poll_task_url": f"/api/v1/search/tasks/{batch_id}",
            "poll_result_url": f"/api/v1/search/tasks/{batch_id}/result?page={req.page}&size={req.size}",
        }
    )


@router.get("/tasks/{batch_id}", response_model=APIResponse)
def get_search_task(batch_id: str, db: Session = Depends(get_db)) -> APIResponse:
    row = db.execute(
        text("SELECT * FROM xhs_crawl_log WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="task not found")

    data = dict(row)
    for key in ("created_at", "updated_at", "completed_at"):
        if data.get(key):
            data[key] = data[key].isoformat()

    return APIResponse(data=data)


@router.get("/tasks/{batch_id}/result", response_model=APIResponse)
def get_search_result(
    batch_id: str,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
) -> APIResponse:
    task_row = db.execute(
        text("SELECT * FROM xhs_crawl_log WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).mappings().first()

    if not task_row:
        raise HTTPException(status_code=404, detail="task not found")

    task = dict(task_row)
    page_data = _get_search_result_page(
        db,
        batch_id=batch_id,
        page=page,
        size=size,
    )

    for key in ("created_at", "updated_at", "completed_at"):
        if task.get(key):
            task[key] = task[key].isoformat()

    return APIResponse(
        data={
            "batch_id": batch_id,
            "status": task["status"],
            "keyword": task.get("keyword"),
            "task": task,
            **page_data,
        }
    )


@router.post("/influencer", response_model=APIResponse)
def search_influencer(req: InfluencerSearchRequest, db: Session = Depends(get_db)) -> APIResponse:
    query = req.query.strip()
    result_cache_key = _result_cache_key(
        "influencer",
        {
            "query": query,
            "industry": req.industry,
            "follower_range": req.follower_range,
            "interaction_range": req.interaction_range,
            "date_range": req.date_range,
            "page": req.page,
            "size": req.size,
            "sort": req.sort,
            "order": req.order,
        },
    )
    if not req.force_refresh:
        cached = _read_result_cache(result_cache_key)
        if cached:
            return APIResponse(data=cached)
    legacy_result: dict | None = None
    v2_result: dict | None = None

    if settings.search_v2_enabled:
        try:
            v2_result = query_influencers_db_first_v2(
                db,
                query=query,
                industry=req.industry,
                follower_range=req.follower_range,
                interaction_range=req.interaction_range,
                date_range=req.date_range,
                page=req.page,
                size=req.size,
                freshness_hours=req.freshness_hours,
                sort=req.sort,
                order=req.order,
                include_notes=req.include_notes,
            )
        except Exception:
            db.rollback()
            if settings.search_v2_fallback_on_error:
                legacy_result = query_influencers_db_first(
                    db,
                    query=query,
                    industry=req.industry,
                    follower_range=req.follower_range,
                    interaction_range=req.interaction_range,
                    date_range=req.date_range,
                    page=req.page,
                    size=req.size,
                    freshness_hours=req.freshness_hours,
                    sort=req.sort,
                    order=req.order,
                    include_notes=req.include_notes,
                )
            else:
                raise HTTPException(status_code=503, detail="search_v2_unavailable")
        result = v2_result or legacy_result
        if settings.search_v2_dual_read and v2_result is not None:
            try:
                legacy_result = query_influencers_db_first(
                    db,
                    query=query,
                    industry=req.industry,
                    follower_range=req.follower_range,
                    interaction_range=req.interaction_range,
                    date_range=req.date_range,
                    page=req.page,
                    size=req.size,
                    freshness_hours=req.freshness_hours,
                    sort=req.sort,
                    order=req.order,
                    include_notes=req.include_notes,
                )
            except Exception:
                db.rollback()
                legacy_result = None
    else:
        legacy_result = query_influencers_db_first(
            db,
            query=query,
            industry=req.industry,
            follower_range=req.follower_range,
            interaction_range=req.interaction_range,
            date_range=req.date_range,
            page=req.page,
            size=req.size,
            freshness_hours=req.freshness_hours,
            sort=req.sort,
            order=req.order,
            include_notes=req.include_notes,
        )
        result = legacy_result
        if settings.search_v2_dual_read:
            try:
                v2_result = query_influencers_db_first_v2(
                    db,
                    query=query,
                    industry=req.industry,
                    follower_range=req.follower_range,
                    interaction_range=req.interaction_range,
                    date_range=req.date_range,
                    page=req.page,
                    size=req.size,
                    freshness_hours=req.freshness_hours,
                    sort=req.sort,
                    order=req.order,
                    include_notes=req.include_notes,
                )
            except Exception:
                db.rollback()
                v2_result = None

    if not result:
        raise HTTPException(status_code=503, detail="search_unavailable")

    should_backfill, health = _should_schedule_background_backfill(
        result,
        force_refresh=req.force_refresh,
        min_results=max(settings.search_min_healthy_results, 30),
        page_size=req.size,
    )
    if settings.search_v2_dual_read and v2_result is not None:
        health["dual_read_compare"] = {
            "legacy_total": int(((legacy_result or {}).get("pagination") or {}).get("total") or 0),
            "v2_total": int((v2_result.get("pagination") or {}).get("total") or 0),
        }
    if result["hit"]:
        if should_backfill:
            _safe_schedule_backfill(
                _schedule_influencer_backfill_job,
                db,
                context="influencer_hit_background_refresh",
                query=query,
                industry=req.industry,
                date_range=req.date_range,
                request_payload=req.model_dump(),
                wait_ms_if_locked=0,
            )
        payload = _add_result_meta(
            {
                "mode": "cache",
                "status": "ready",
                "search_type": "influencer",
                "query": query,
                **result,
            },
            health=health,
            pending=False,
        )
        _write_result_cache(
            result_cache_key,
            payload,
            ttl_seconds=int(getattr(settings, "search_result_cache_ttl_seconds", 60)),
        )
        return APIResponse(data=payload)

    job = _safe_schedule_backfill(
        _schedule_influencer_backfill_job,
        db,
        context="influencer_pending_backfill",
        query=query,
        industry=req.industry,
        date_range=req.date_range,
        request_payload=req.model_dump(),
        wait_ms_if_locked=settings.search_coalesce_wait_ms,
    )
    if not job:
        failed_payload = _add_result_meta(
            {
                "mode": "cache",
                "status": "failed",
                "search_type": "influencer",
                "query": query,
                **result,
            },
            health=health,
            pending=False,
        )
        return APIResponse(data=failed_payload)

    pending_payload = _add_result_meta(
        {
            "mode": "async",
            "status": "pending",
            "search_type": "influencer",
            "query": query,
            "job_id": job["job_id"],
            "task_id": job.get("task_id"),
            "poll_job_url": f"/api/v1/search/jobs/{job['job_id']}",
            **result,
        },
        health=health,
        pending=True,
    )
    return APIResponse(data=pending_payload)


@router.post("/brand-category", response_model=APIResponse)
def search_brand_or_category(req: BrandCategorySearchRequest, db: Session = Depends(get_db)) -> APIResponse:
    query = req.query.strip()
    effective_mode: str = "brand" if _should_use_brand_mode(db, query=query, requested_mode=req.mode, industry=req.industry) else req.mode
    date_range = 90 if req.mode == "category" and req.industry else req.date_range
    result_cache_key = _result_cache_key(
        "brand_category",
        {
            "query": query,
            "mode": effective_mode,
            "industry": req.industry,
            "min_like": req.min_like,
            "date_range": date_range,
            "page": req.page,
            "size": req.size,
            "sort": req.sort,
            "order": req.order,
        },
    )
    if not req.force_refresh:
        cached = _read_result_cache(result_cache_key)
        if cached:
            return APIResponse(data=cached)

    def run_legacy_query() -> dict:
        return query_brand_category_db_first(
            db,
            query=query,
            mode=effective_mode,  # type: ignore[arg-type]
            industry=req.industry,
            min_like=req.min_like,
            date_range=date_range,
            page=req.page,
            size=req.size,
            freshness_hours=req.freshness_hours,
            sort=req.sort,
            order=req.order,
            fast_pagination=req.page > 1,
        )

    legacy_result: dict | None = None
    v2_result: dict | None = None
    result_source = "legacy_only"
    recall_guard_triggered = False
    recall_guard_fallback = False
    if settings.search_v2_enabled:
        try:
            v2_result = query_brand_category_db_first_v2(
                db,
                query=query,
                mode=effective_mode,  # type: ignore[arg-type]
                industry=req.industry,
                min_like=req.min_like,
                date_range=date_range,
                page=req.page,
                size=req.size,
                freshness_hours=req.freshness_hours,
                sort=req.sort,
                order=req.order,
            )
        except Exception:
            db.rollback()
            if settings.search_v2_fallback_on_error:
                legacy_result = run_legacy_query()
            else:
                raise HTTPException(status_code=503, detail="search_v2_unavailable")
        if v2_result is not None:
            result = v2_result
            result_source = "v2"
            recall_guard_triggered = _should_run_v2_recall_guard(
                query=query,
                v2_result=v2_result,
                page_size=req.size,
                page=req.page,
            )
            if recall_guard_triggered and legacy_result is None:
                try:
                    legacy_result = run_legacy_query()
                except Exception:
                    db.rollback()
                    legacy_result = None
            if _should_prefer_legacy_for_recall_guard(v2_result=v2_result, legacy_result=legacy_result):
                result = legacy_result
                result_source = "legacy_recall_guard"
                recall_guard_fallback = True
        else:
            result = legacy_result
            result_source = "legacy_v2_error"

        if settings.search_v2_dual_read and v2_result is not None and legacy_result is None:
            try:
                legacy_result = run_legacy_query()
            except Exception:
                db.rollback()
                legacy_result = None
    else:
        legacy_result = run_legacy_query()
        result = legacy_result
        result_source = "legacy"
        if settings.search_v2_dual_read:
            try:
                v2_result = query_brand_category_db_first_v2(
                    db,
                    query=query,
                    mode=effective_mode,  # type: ignore[arg-type]
                    industry=req.industry,
                    min_like=req.min_like,
                    date_range=date_range,
                    page=req.page,
                    size=req.size,
                    freshness_hours=req.freshness_hours,
                    sort=req.sort,
                    order=req.order,
                )
            except Exception:
                db.rollback()
                v2_result = None

    if not result:
        raise HTTPException(status_code=503, detail="search_unavailable")

    should_backfill, health = _should_schedule_background_backfill(
        result,
        force_refresh=req.force_refresh,
        min_results=max(settings.search_min_healthy_results, 30),
        page_size=req.size,
    )
    if settings.search_v2_dual_read and v2_result is not None:
        health["dual_read_compare"] = {
            "legacy_total": int(((legacy_result or {}).get("pagination") or {}).get("total") or 0),
            "v2_total": int((v2_result.get("pagination") or {}).get("total") or 0),
        }
    if v2_result is not None and settings.search_v2_recall_guard_enabled:
        health["recall_guard"] = {
            "enabled": True,
            "triggered": bool(recall_guard_triggered),
            "fallback_to_legacy": bool(recall_guard_fallback),
            "selected_source": result_source,
            "v2_total": _result_total(v2_result),
            "legacy_total": _result_total(legacy_result),
        }
    if result["hit"]:
        if should_backfill:
            _safe_schedule_backfill(
                _schedule_brand_category_backfill_job,
                db,
                context="brand_category_hit_background_refresh",
                query=query,
                mode=effective_mode,
                industry=req.industry,
                date_range=date_range,
                request_payload={**req.model_dump(), "mode": effective_mode, "date_range": date_range},
                wait_ms_if_locked=0,
            )
        payload = _add_result_meta(
            {
                "mode": "cache",
                "status": "ready",
                "search_type": "brand_category",
                "query": query,
                "mode_type": effective_mode,
                **result,
            },
            health=health,
            pending=False,
        )
        _write_result_cache(
            result_cache_key,
            payload,
            ttl_seconds=int(getattr(settings, "search_result_cache_ttl_seconds", 60)),
        )
        return APIResponse(data=payload)

    job = _safe_schedule_backfill(
        _schedule_brand_category_backfill_job,
        db,
        context="brand_category_pending_backfill",
        query=query,
        mode=effective_mode,
        industry=req.industry,
        date_range=date_range,
        request_payload={**req.model_dump(), "mode": effective_mode, "date_range": date_range},
        wait_ms_if_locked=settings.search_coalesce_wait_ms,
    )
    if not job:
        failed_payload = _add_result_meta(
            {
                "mode": "cache",
                "status": "failed",
                "search_type": "brand_category",
                "query": query,
                "mode_type": effective_mode,
                **result,
            },
            health=health,
            pending=False,
        )
        return APIResponse(data=failed_payload)

    pending_payload = _add_result_meta(
        {
            "mode": "async",
            "status": "pending",
            "search_type": "brand_category",
            "query": query,
            "mode_type": effective_mode,
            "job_id": job["job_id"],
            "task_id": job.get("task_id"),
            "poll_job_url": f"/api/v1/search/jobs/{job['job_id']}",
            **result,
        },
        health=health,
        pending=True,
    )
    return APIResponse(data=pending_payload)


@router.get("/jobs/{job_id}", response_model=APIResponse)
def get_unified_search_job(
    job_id: str,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
) -> APIResponse:
    job = try_sync_job_status_with_crawl(db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    status = job["status"]
    payload = _safe_payload(job.get("request_payload"))
    search_type = str(job.get("search_type") or "")
    query = str(job.get("query") or "")

    if status == "ready":
        response_payload = _safe_payload(job.get("response_payload"))
        response_row_count = int(response_payload.get("row_count") or 0)
        if response_row_count <= 0:
            mark_search_job_failed(db, job_id=job_id, error_msg="no_results_after_fetch")
            return APIResponse(
                data=_add_result_meta(
                    {
                        "job_id": job_id,
                        "status": "failed",
                        "search_type": search_type,
                        "query": query,
                    },
                    health={"reasons": ["no_results_after_fetch"], "healthy": False, "total": 0, "freshness": None},
                    pending=False,
                    pending_reason="no_results_after_fetch",
                )
            )
        if search_type == "influencer":
            if settings.search_v2_enabled:
                try:
                    result = query_influencers_db_first_v2(
                        db,
                        query=query,
                        industry=payload.get("industry"),
                        follower_range=payload.get("follower_range"),
                        interaction_range=payload.get("interaction_range"),
                        date_range=int(payload.get("date_range") or 30),
                        page=page,
                        size=size,
                        freshness_hours=int(payload.get("freshness_hours") or 24),
                        sort=str(payload.get("sort") or "relevance"),  # type: ignore[arg-type]
                        order=str(payload.get("order") or "desc"),  # type: ignore[arg-type]
                        include_notes=bool(payload.get("include_notes") or False),
                    )
                except Exception:
                    db.rollback()
                    if not settings.search_v2_fallback_on_error:
                        raise HTTPException(status_code=503, detail="search_v2_unavailable")
                    result = query_influencers_db_first(
                        db,
                        query=query,
                        industry=payload.get("industry"),
                        follower_range=payload.get("follower_range"),
                        interaction_range=payload.get("interaction_range"),
                        date_range=int(payload.get("date_range") or 30),
                        page=page,
                        size=size,
                        freshness_hours=int(payload.get("freshness_hours") or 24),
                        sort=str(payload.get("sort") or "relevance"),  # type: ignore[arg-type]
                        order=str(payload.get("order") or "desc"),  # type: ignore[arg-type]
                        include_notes=bool(payload.get("include_notes") or False),
                    )
            else:
                result = query_influencers_db_first(
                    db,
                    query=query,
                    industry=payload.get("industry"),
                    follower_range=payload.get("follower_range"),
                    interaction_range=payload.get("interaction_range"),
                    date_range=int(payload.get("date_range") or 30),
                    page=page,
                    size=size,
                    freshness_hours=int(payload.get("freshness_hours") or 24),
                    sort=str(payload.get("sort") or "relevance"),  # type: ignore[arg-type]
                    order=str(payload.get("order") or "desc"),  # type: ignore[arg-type]
                    include_notes=bool(payload.get("include_notes") or False),
                )
        else:
            mode = str(payload.get("mode") or "brand")
            industry = payload.get("industry")
            min_like = int(payload.get("min_like") or 0)
            date_range = int(payload.get("date_range") or 30)
            freshness_hours = int(payload.get("freshness_hours") or 24)
            sort = str(payload.get("sort") or "stat")
            order = str(payload.get("order") or "desc")

            def run_legacy_brand_category() -> dict:
                return query_brand_category_db_first(
                    db,
                    query=query,
                    mode=mode,  # type: ignore[arg-type]
                    industry=industry,
                    min_like=min_like,
                    date_range=date_range,
                    page=page,
                    size=size,
                    freshness_hours=freshness_hours,
                    sort=sort,  # type: ignore[arg-type]
                    order=order,  # type: ignore[arg-type]
                    fast_pagination=page > 1,
                )

            if settings.search_v2_enabled:
                v2_result: dict | None = None
                try:
                    v2_result = query_brand_category_db_first_v2(
                        db,
                        query=query,
                        mode=mode,  # type: ignore[arg-type]
                        industry=industry,
                        min_like=min_like,
                        date_range=date_range,
                        page=page,
                        size=size,
                        freshness_hours=freshness_hours,
                        sort=sort,  # type: ignore[arg-type]
                        order=order,  # type: ignore[arg-type]
                    )
                except Exception:
                    db.rollback()
                    if not settings.search_v2_fallback_on_error:
                        raise HTTPException(status_code=503, detail="search_v2_unavailable")
                    result = run_legacy_brand_category()
                else:
                    result = v2_result
                    if _should_run_v2_recall_guard(
                        query=query,
                        v2_result=v2_result,
                        page_size=size,
                        page=page,
                    ):
                        try:
                            legacy_result = run_legacy_brand_category()
                        except Exception:
                            db.rollback()
                            legacy_result = None
                        if _should_prefer_legacy_for_recall_guard(v2_result=v2_result, legacy_result=legacy_result):
                            result = legacy_result  # type: ignore[assignment]
            else:
                result = run_legacy_brand_category()
        health = _needs_backfill(result, force_refresh=False)[1]
        if _should_keep_pending_until_first_page_full(result, page_size=size):
            return APIResponse(
                data=_add_result_meta(
                    {
                        "job_id": job_id,
                        "status": "pending",
                        "search_type": search_type,
                        "query": query,
                    },
                    health=health,
                    pending=True,
                    pending_reason="waiting_for_first_page",
                )
            )
        ready_payload = _add_result_meta(
            {
                "job_id": job_id,
                "status": "ready",
                "search_type": search_type,
                "query": query,
                **result,
            },
            health=health,
            pending=False,
        )
        return APIResponse(
            data=ready_payload
        )

    pending_reason = str(job.get("error_msg") or "") if status == "failed" else "job_running"
    return APIResponse(
        data=_add_result_meta(
            {
            "job_id": job_id,
            "status": status,
            "search_type": search_type,
            "query": query,
            "task_id": job.get("task_id"),
            "crawl_batch_id": job.get("crawl_batch_id"),
            "error_msg": job.get("error_msg"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "completed_at": job.get("completed_at"),
            },
            health={"reasons": [status], "healthy": status == "ready", "total": 0, "freshness": None},
            pending=status in {"pending", "running"},
            pending_reason=pending_reason or status,
        ),
    )
