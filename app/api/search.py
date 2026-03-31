from __future__ import annotations

import hashlib
import json
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
    mark_search_job_running,
    query_brand_category_db_first,
    query_influencers_db_first,
    try_sync_job_status_with_crawl,
)
from app.services.ingest import create_crawl_log
from app.services.industry_catalog import resolve_industry_key
from app.tasks.jobs import run_search_notes, trigger_anchor_info, trigger_fans_portrait

router = APIRouter(prefix="/search", tags=["search"])
settings = get_settings()

_redis_client: Redis | None = None
_last_stale_recover_at: datetime | None = None
_RECOVER_TASK_TYPES = ("note_info", "note_comment", "anchor_info", "fans_portrait")


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
    job = get_search_job(db, job_id)
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


def _needs_backfill(result: dict, *, force_refresh: bool) -> tuple[bool, dict]:
    decision = build_fetch_decision(
        result,
        force_refresh=force_refresh,
        min_results=settings.search_min_healthy_results,
        stale_hours=settings.search_stale_hours,
    )
    health = dict(decision["health"])
    health["reasons"] = decision["reasons"]
    return bool(decision["need_fetch"]), health


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
                SET status = 'failed',
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
                    "trigger_comments": True,
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
    if req.force_refresh:
        _recover_stale_running_collect_tasks(db)
    result = query_influencers_db_first(
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
    )
    _enqueue_creator_profile_backfill(db, result.get("items") or [])
    _enqueue_creator_note_backfill(db, result.get("items") or [])
    should_backfill, health = _needs_backfill(result, force_refresh=req.force_refresh)
    if result["hit"] and not should_backfill:
        payload = {
            "mode": "cache",
            "status": "ready",
            "search_type": "influencer",
            "query": query,
            "health": health,
            **result,
        }
        _write_result_cache(
            result_cache_key,
            payload,
            ttl_seconds=int(getattr(settings, "search_result_cache_ttl_seconds", 60)),
        )
        return APIResponse(data=payload)

    cache_key = _coalesce_cache_key(
        search_type="influencer",
        query=query,
        mode=None,
        industry=req.industry,
        date_range=req.date_range,
    )
    lock_key = f"{cache_key}:lock"
    redis_client = _get_redis_client()

    reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=0)
    if reused_job:
        return APIResponse(
            data={
                "mode": "async",
                "status": "pending",
                "search_type": "influencer",
                "query": query,
                "job_id": reused_job["job_id"],
                "task_id": reused_job.get("task_id"),
                "health": health,
                **result,
            }
        )

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
        reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=settings.search_coalesce_wait_ms)
        if reused_job:
            return APIResponse(
                data={
                    "mode": "async",
                    "status": "pending",
                    "search_type": "influencer",
                    "query": query,
                    "job_id": reused_job["job_id"],
                    "task_id": reused_job.get("task_id"),
                    "health": health,
                    **result,
                }
            )

    try:
        job_id = create_search_job(
            db,
            search_type="influencer",
            query=query,
            mode=None,
            industry=req.industry,
            request_payload=req.model_dump(),
        )
        batch_id = uuid.uuid4().hex[:16]
        trigger_task = run_search_notes.apply_async(
            kwargs={
                "batch_id": batch_id,
                "keyword": query or str(req.industry or "小红书"),
                "sort": 1,
                "max_items": 240,
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
    finally:
        if redis_client and lock_acquired:
            try:
                current = redis_client.get(lock_key)
                if current == lock_token:
                    redis_client.delete(lock_key)
            except RedisError:
                pass

    return APIResponse(
        data={
            "mode": "async",
            "status": "pending",
            "search_type": "influencer",
            "query": query,
            "job_id": job_id,
            "task_id": trigger_task.id,
            "health": health,
            "poll_job_url": f"/api/v1/search/jobs/{job_id}",
            **result,
        }
    )


@router.post("/brand-category", response_model=APIResponse)
def search_brand_or_category(req: BrandCategorySearchRequest, db: Session = Depends(get_db)) -> APIResponse:
    query = req.query.strip()
    date_range = 90 if req.mode == "category" and req.industry else req.date_range
    result_cache_key = _result_cache_key(
        "brand_category",
        {
            "query": query,
            "mode": req.mode,
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
    if req.force_refresh:
        _recover_stale_running_collect_tasks(db)
    result = query_brand_category_db_first(
        db,
        query=query,
        mode=req.mode,
        industry=req.industry,
        min_like=req.min_like,
        date_range=date_range,
        page=req.page,
        size=req.size,
        freshness_hours=req.freshness_hours,
        sort=req.sort,
        order=req.order,
    )
    should_backfill, health = _needs_backfill(result, force_refresh=req.force_refresh)
    if result["hit"] and not should_backfill:
        payload = {
            "mode": "cache",
            "status": "ready",
            "search_type": "brand_category",
            "query": query,
            "mode_type": req.mode,
            "health": health,
            **result,
        }
        _write_result_cache(
            result_cache_key,
            payload,
            ttl_seconds=int(getattr(settings, "search_result_cache_ttl_seconds", 60)),
        )
        return APIResponse(data=payload)

    cache_key = _coalesce_cache_key(
        search_type="brand_category",
        query=query,
        mode=req.mode,
        industry=req.industry,
        date_range=date_range,
    )
    lock_key = f"{cache_key}:lock"
    redis_client = _get_redis_client()

    reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=0)
    if reused_job:
        return APIResponse(
            data={
                "mode": "async",
                "status": "pending",
                "search_type": "brand_category",
                "query": query,
                "mode_type": req.mode,
                "job_id": reused_job["job_id"],
                "task_id": reused_job.get("task_id"),
                "health": health,
                **result,
            }
        )

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
        reused_job = _try_reuse_coalesced_job(db, cache_key=cache_key, wait_ms=settings.search_coalesce_wait_ms)
        if reused_job:
            return APIResponse(
                data={
                    "mode": "async",
                    "status": "pending",
                    "search_type": "brand_category",
                    "query": query,
                    "mode_type": req.mode,
                    "job_id": reused_job["job_id"],
                    "task_id": reused_job.get("task_id"),
                    "health": health,
                    **result,
                }
            )

    try:
        job_id = create_search_job(
            db,
            search_type="brand_category",
            query=query,
            mode=req.mode,
            industry=req.industry,
            request_payload={**req.model_dump(), "date_range": date_range},
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
    finally:
        if redis_client and lock_acquired:
            try:
                current = redis_client.get(lock_key)
                if current == lock_token:
                    redis_client.delete(lock_key)
            except RedisError:
                pass

    return APIResponse(
        data={
            "mode": "async",
            "status": "pending",
            "search_type": "brand_category",
            "query": query,
            "mode_type": req.mode,
            "job_id": job_id,
            "task_id": trigger_task.id,
            "health": health,
            "poll_job_url": f"/api/v1/search/jobs/{job_id}",
            **result,
        }
    )


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
        if search_type == "influencer":
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
                sort=str(payload.get("sort") or "followers"),  # type: ignore[arg-type]
                order=str(payload.get("order") or "desc"),  # type: ignore[arg-type]
            )
        else:
            result = query_brand_category_db_first(
                db,
                query=query,
                mode=str(payload.get("mode") or "brand"),
                industry=payload.get("industry"),
                min_like=int(payload.get("min_like") or 0),
                date_range=int(payload.get("date_range") or 30),
                page=page,
                size=size,
                freshness_hours=int(payload.get("freshness_hours") or 24),
                sort=str(payload.get("sort") or "stat"),  # type: ignore[arg-type]
                order=str(payload.get("order") or "desc"),  # type: ignore[arg-type]
            )
        return APIResponse(
            data={
                "job_id": job_id,
                "status": "ready",
                "search_type": search_type,
                "query": query,
                **result,
            }
        )

    return APIResponse(
        data={
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
        }
    )
