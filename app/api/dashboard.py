from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import APIResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
settings = get_settings()
_dashboard_redis_client: Redis | None = None
_dashboard_memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_DASHBOARD_CACHE_TTL_SECONDS = 60


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _rows_to_items(rows):
    items = []
    for row in rows:
        items.append({k: _jsonable(v) for k, v in dict(row).items()})
    return items


def _get_redis_client() -> Redis | None:
    global _dashboard_redis_client
    if _dashboard_redis_client is not None:
        return _dashboard_redis_client
    try:
        _dashboard_redis_client = Redis.from_url(settings.celery_broker_url, decode_responses=True, socket_timeout=1)
        _dashboard_redis_client.ping()
    except Exception:
        _dashboard_redis_client = None
    return _dashboard_redis_client


def _cache_get(key: str) -> dict[str, Any] | None:
    now_ts = time.time()
    cached = _dashboard_memory_cache.get(key)
    if cached and cached[0] > now_ts:
        return json.loads(json.dumps(cached[1], ensure_ascii=False, default=_jsonable))

    redis_client = _get_redis_client()
    if not redis_client:
        return None
    try:
        raw = redis_client.get(key)
    except RedisError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    _dashboard_memory_cache[key] = (now_ts + _DASHBOARD_CACHE_TTL_SECONDS, payload)
    return payload


def _cache_set(key: str, payload: dict[str, Any], *, ttl_seconds: int = _DASHBOARD_CACHE_TTL_SECONDS) -> None:
    expires_at = time.time() + max(1, ttl_seconds)
    _dashboard_memory_cache[key] = (expires_at, payload)
    redis_client = _get_redis_client()
    if not redis_client:
        return
    try:
        redis_client.set(key, json.dumps(payload, ensure_ascii=False, default=_jsonable), ex=max(1, ttl_seconds))
    except RedisError:
        return


def _load_trend_window_base(db: Session, days: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            WITH series AS (
                SELECT generate_series(
                    current_date - (:days - 1) * INTERVAL '1 day',
                    current_date,
                    INTERVAL '1 day'
                )::date AS stat_date
            ),
            daily AS (
                SELECT
                    DATE(COALESCE(publish_time, created_at)) AS stat_date,
                    COUNT(*)::bigint AS new_count
                FROM xhs_note_fact
                WHERE DATE(COALESCE(publish_time, created_at)) >= current_date - (:days - 1) * INTERVAL '1 day'
                GROUP BY 1
            ),
            joined AS (
                SELECT
                    s.stat_date,
                    COALESCE(d.new_count, 0)::bigint AS new_count
                FROM series s
                LEFT JOIN daily d ON d.stat_date = s.stat_date
            )
            SELECT
                stat_date,
                new_count,
                SUM(new_count) OVER (ORDER BY stat_date ASC ROWS UNBOUNDED PRECEDING)::bigint AS total_count
            FROM joined
            ORDER BY stat_date ASC
            """
        ),
        {"days": days},
    ).mappings().all()

    return _rows_to_items(rows)


def _slice_trend_window(rows: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    return rows[-days:] if len(rows) > days else rows


@router.get("/beauty/categories", response_model=APIResponse)
def beauty_categories(db: Session = Depends(get_db)) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT
                t.category_name,
                COUNT(*) AS total_posts
            FROM xhs_note_fact f
            JOIN xhs_beauty_taxonomy_dim t
              ON f.search_keyword = ANY(t.keywords)
            WHERE t.status = 'enabled'
            GROUP BY t.category_name, t.sort_no
            ORDER BY total_posts DESC, t.sort_no ASC, t.category_name ASC
            """
        )
    ).mappings().all()

    return APIResponse(data={"items": _rows_to_items(rows)})


@router.get("/beauty/trend", response_model=APIResponse)
def beauty_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT
                DATE(COALESCE(f.publish_time, f.created_at)) AS stat_date,
                t.category_name,
                COUNT(*) AS total_posts
            FROM xhs_note_fact f
            JOIN xhs_beauty_taxonomy_dim t
              ON f.search_keyword = ANY(t.keywords)
            WHERE COALESCE(f.publish_time, f.created_at) >= now() - (:days || ' day')::interval
              AND t.status = 'enabled'
            GROUP BY DATE(COALESCE(f.publish_time, f.created_at)), t.category_name, t.sort_no
            ORDER BY stat_date ASC, t.sort_no ASC, t.category_name ASC
            """
        ),
        {"days": days},
    ).mappings().all()

    return APIResponse(data={"items": _rows_to_items(rows)})


@router.get("/beauty/brands", response_model=APIResponse)
def beauty_brands(db: Session = Depends(get_db)) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT
                brand_name,
                note_count AS mention_count,
                creator_count,
                like_total,
                comment_total,
                collection_total
            FROM xhs_brand_center_view
            ORDER BY mention_count DESC, like_total DESC, brand_name ASC
            """
        )
    ).mappings().all()

    return APIResponse(data={"items": _rows_to_items(rows)})


@router.get("/beauty/posts", response_model=APIResponse)
def beauty_posts(
    limit: int = Query(default=20, ge=1, le=200),
    min_like: int = Query(default=100, ge=0),
    keyword: str | None = Query(default=None),
    brand_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> APIResponse:
    keyword_filter = keyword or ""
    brand_filter = brand_name or ""
    rows = db.execute(
        text(
            """
            SELECT
                f.note_id AS post_id,
                'xiaohongshu' AS platform,
                f.publish_time,
                'https://www.xiaohongshu.com/explore/' || f.note_id AS post_url,
                f.title,
                COALESCE(f.content, '') AS content,
                f.media_type,
                f.duration_seconds,
                f.tags,
                f.media_urls,
                f.cover_image_url,
                f.author_id,
                f.author_nickname,
                COALESCE(f.author_fans_count, 0) AS author_fans_count,
                f.search_keyword AS category_name,
                COALESCE(f.like_count, 0) AS like_count,
                COALESCE(f.collection_count, 0) AS collection_count,
                COALESCE(f.comment_count, 0) AS comment_count,
                COALESCE(f.share_count, 0) AS share_count,
                COALESCE(f.read_count, 0) AS read_count,
                COALESCE(f.stat_count, 0) AS stat_count,
                COALESCE(f.exp_count, 0) AS exp_count,
                (
                    COALESCE(f.like_count, 0)
                  + COALESCE(f.collection_count, 0)
                  + COALESCE(f.comment_count, 0)
                  + COALESCE(f.share_count, 0)
                ) AS interaction_total
            FROM xhs_note_fact f
            WHERE COALESCE(f.like_count, 0) >= :min_like
              AND (:keyword = '' OR f.search_keyword = :keyword)
              AND (
                    :brand_name = ''
                 OR EXISTS (
                        SELECT 1
                        FROM xhs_note_brand_rel rel
                        WHERE rel.note_id = f.note_id
                          AND rel.brand_name = :brand_name
                    )
              )
            ORDER BY
                (
                    COALESCE(f.like_count, 0)
                  + COALESCE(f.collection_count, 0)
                  + COALESCE(f.comment_count, 0)
                  + COALESCE(f.share_count, 0)
                ) DESC,
                f.publish_time DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"limit": limit, "min_like": min_like, "keyword": keyword_filter, "brand_name": brand_filter},
    ).mappings().all()

    return APIResponse(data={"items": _rows_to_items(rows)})


@router.get("/xhs/overview", response_model=APIResponse)
def xhs_overview(
    days: int = Query(default=90, ge=30, le=365),
    db: Session = Depends(get_db),
) -> APIResponse:
    window_max = max(days, 90)
    cache_key = f"xhs:dashboard:overview:{window_max}"
    cached = _cache_get(cache_key)
    if cached:
        return APIResponse(data=cached)

    summary_row = db.execute(
        text(
            """
            SELECT
                COUNT(*)::bigint AS notes_total,
                COUNT(*) FILTER (WHERE COALESCE(like_count, 0) >= 100)::bigint AS notes_like_ge_100,
                COUNT(DISTINCT NULLIF(author_id, ''))::bigint AS creators_total,
                (SELECT COUNT(*)::bigint FROM xhs_comment_fact) AS comments_total
            FROM xhs_note_fact
            """
        )
    ).mappings().first()

    summary = dict(summary_row or {})

    trend_base = _load_trend_window_base(db, window_max)
    trend = {
        "7": _slice_trend_window(trend_base, 7),
        "30": _slice_trend_window(trend_base, 30),
        "90": _slice_trend_window(trend_base, 90),
    }

    industries = db.execute(
        text(
            """
            SELECT
                i.industry_key,
                i.industry_name,
                i.sort_no,
                COALESCE(c.note_count, 0)::bigint AS note_count
            FROM xhs_industry_dim i
            LEFT JOIN (
                SELECT industry_key, COUNT(*)::bigint AS note_count
                FROM xhs_note_industry_rel
                GROUP BY industry_key
            ) c ON c.industry_key = i.industry_key
            WHERE COALESCE(i.status, 'enabled') = 'enabled'
            ORDER BY i.sort_no ASC, i.industry_name ASC
            """
        )
    ).mappings().all()

    payload = {
        "summary": _jsonable(summary),
        "trend": trend,
        "industries": _rows_to_items(industries),
        "generated_at": datetime.utcnow().isoformat(),
    }
    _cache_set(cache_key, payload)

    return APIResponse(data=payload)


@router.get("/xhs/live", response_model=APIResponse)
def xhs_live(db: Session = Depends(get_db)) -> APIResponse:
    metrics_row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE created_at >= now() - interval '24 hours'
                )::bigint AS new_notes_24h,
                COUNT(*) FILTER (
                    WHERE updated_at >= now() - interval '30 minutes'
                      AND updated_at > created_at
                )::bigint AS updated_notes_30m
            FROM xhs_note_fact
            """
        )
    ).mappings().first()

    comments_row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE created_at >= now() - interval '30 minutes'
                )::bigint AS new_comments_30m
            FROM xhs_comment_fact
            """
        )
    ).mappings().first()

    jobs_row = db.execute(
        text(
            """
            SELECT COUNT(*)::bigint AS jobs_running
            FROM xhs_crawl_log
            WHERE status = 'running'
            """
        )
    ).mappings().first()

    metrics = dict(metrics_row or {})
    metrics["new_comments_30m"] = int((comments_row or {}).get("new_comments_30m") or 0)
    metrics["jobs_running"] = int((jobs_row or {}).get("jobs_running") or 0)
    metrics["generated_at"] = datetime.utcnow().isoformat()

    return APIResponse(data=_jsonable(metrics))


@router.get("/xhs/live-totals", response_model=APIResponse)
def xhs_live_totals(db: Session = Depends(get_db)) -> APIResponse:
    totals_row = db.execute(
        text(
            """
            SELECT
                COUNT(*)::bigint AS notes_total,
                COUNT(DISTINCT NULLIF(author_id, ''))::bigint AS creators_total,
                (SELECT COUNT(*)::bigint FROM xhs_comment_fact) AS comments_total
            FROM xhs_note_fact
            """
        )
    ).mappings().first()

    totals = dict(totals_row or {})
    totals["generated_at"] = datetime.utcnow().isoformat()
    return APIResponse(data=_jsonable(totals))


@router.get("/xhs/live-industries", response_model=APIResponse)
def xhs_live_industries(db: Session = Depends(get_db)) -> APIResponse:
    cache_key = "xhs:dashboard:live-industries"
    cached = _cache_get(cache_key)
    if cached:
        return APIResponse(data=cached)

    rows = db.execute(
        text(
            """
            SELECT
                i.industry_key,
                i.industry_name,
                COALESCE(c.note_count, 0)::bigint AS note_count
            FROM xhs_industry_dim i
            LEFT JOIN (
                SELECT industry_key, COUNT(*)::bigint AS note_count
                FROM xhs_note_industry_rel
                GROUP BY industry_key
            ) c ON c.industry_key = i.industry_key
            WHERE COALESCE(i.status, 'enabled') = 'enabled'
            ORDER BY i.sort_no ASC, i.industry_name ASC
            """
        )
    ).mappings().all()

    payload = {
        "items": _rows_to_items(rows),
        "generated_at": datetime.utcnow().isoformat(),
    }
    _cache_set(cache_key, payload)
    return APIResponse(data=payload)


@router.get("/xhs/ingest-health", response_model=APIResponse)
def xhs_ingest_health(db: Session = Depends(get_db)) -> APIResponse:
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

    notes_total = int((row or {}).get("notes_total") or 0)
    classified_notes = int((row or {}).get("classified_notes") or 0)
    unclassified_total = max(0, notes_total - classified_notes)
    classify_coverage = (classified_notes / notes_total) if notes_total > 0 else 0

    return APIResponse(
        data={
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
            "generated_at": datetime.utcnow().isoformat(),
        }
    )

    
