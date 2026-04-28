from __future__ import annotations

import json
import time
import uuid

from requests import HTTPError, RequestException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.services.anchor_links import resolve_anchor_link
from app.services.huitun_client import HuitunClient
from app.services.ingest import (
    create_crawl_log,
    save_anchor_search_results,
    save_search_results,
    upsert_brand_accounts,
    upsert_brand_dim_and_accounts,
)
from app.services.search_center import mark_search_job_failed, mark_search_job_running
from app.tasks.celery_app import celery_app

settings = get_settings()
client = HuitunClient()
_quota_cache: tuple[float, dict[str, object]] | None = None
_quota_cache_ttl_seconds = 300


def _db() -> Session:
    return SessionLocal()


def _callback_url(path: str) -> str:
    return f"{settings.app_public_base_url.rstrip('/')}{settings.api_prefix}{path}"


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (HTTPError, RequestException)):
        return True

    message = str(exc).lower()
    return any(
        token in message
        for token in (
            " 429",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "timed out",
            "connection",
            "当前任务已达上限",
            "任务已达上限",
            "task limit",
            "reached the limit",
        )
    )


def _is_task_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "当前任务已达上限",
            "任务已达上限",
            "task limit",
            "reached the limit",
        )
    )


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "quota",
            "surplus",
            "余额不足",
            "次数不足",
            "剩余次数",
            "调用次数",
            "no remaining",
            "exhausted",
        )
    )


def _get_cached_quota_data() -> dict[str, object] | None:
    global _quota_cache
    now_ts = time.monotonic()
    if _quota_cache and now_ts - _quota_cache[0] < _quota_cache_ttl_seconds:
        return _quota_cache[1]
    try:
        response = client.get_quota()
    except Exception:
        return None
    data = response.get("data") if isinstance(response, dict) else None
    if not isinstance(data, dict):
        return None
    _quota_cache = (now_ts, data)
    return data


def _quota_remaining(task_type: str) -> int | None:
    data = _get_cached_quota_data()
    if not data:
        return None
    raw = data.get(task_type)
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_huitun_quota_exhausted(task_type: str) -> bool:
    remaining = _quota_remaining(task_type)
    return remaining is not None and remaining <= 0


def _retry_later(task, exc: Exception):
    base_delay = settings.huitun_task_retry_delay_seconds
    max_retries = 3
    if _is_task_limit_error(exc):
        # Task-pool saturation needs a longer cooldown; short retries only amplify failures.
        base_delay = max(base_delay, 1800)
        # Provider saturation should not create long retry storms.
        max_retries = 1
    countdown = base_delay * (task.request.retries + 1)
    raise task.retry(exc=exc, countdown=countdown, max_retries=max_retries)


def _resolve_anchor_target(db: Session, anchor_ref: str | None) -> tuple[str | None, str | None]:
    if not anchor_ref:
        return None, None

    anchor_ref = anchor_ref.strip()
    if not anchor_ref:
        return None, None

    row = db.execute(
        text(
            """
            SELECT author_id, anchor_link
            FROM xhs_anchor_dim
            WHERE author_id = :anchor_ref
               OR red_id = :anchor_ref
               OR anchor_link = :anchor_ref
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"anchor_ref": anchor_ref},
    ).mappings().first()

    author_id = (row.get("author_id") if row else None) or (None if anchor_ref.startswith("http") else anchor_ref)
    stored_anchor_link = row.get("anchor_link") if row else None
    anchor_link = resolve_anchor_link(anchor_ref=anchor_ref, stored_anchor_link=stored_anchor_link)
    return author_id, anchor_link


def _recent_note_comment_limit_errors(db: Session, window_minutes: int = 20) -> int:
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


def _log_quota_skipped(
    db: Session,
    *,
    batch_id: str,
    task_type: str,
    note_id: str,
    task_id: str | None,
    back_url: str,
    error: str | None = None,
) -> dict:
    response_payload: dict[str, object] = {
        "skipped": True,
        "reason": "quota_exhausted",
        "quota_remaining": _quota_remaining(task_type),
    }
    if error:
        response_payload["error"] = error
    create_crawl_log(
        db,
        batch_id=batch_id,
        task_type=task_type,
        biz_type="collect",
        status="success",
        note_id=note_id,
        task_id=task_id,
        request_payload={"note_id": note_id, "back_url": back_url},
        response_payload=response_payload,
    )
    db.commit()
    return {"batch_id": batch_id, "skipped": True, "reason": "quota_exhausted"}


def _safe_log_failure(
    db: Session,
    *,
    batch_id: str,
    task_type: str,
    biz_type: str,
    task_id: str | None,
    response_payload: dict[str, object],
    **kwargs: object,
) -> None:
    try:
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type=task_type,
            biz_type=biz_type,
            status="failed",
            task_id=task_id,
            response_payload=response_payload,
            **kwargs,
        )
        db.commit()
    except Exception:
        db.rollback()


def _safe_log_skipped_success(
    db: Session,
    *,
    batch_id: str,
    task_type: str,
    biz_type: str,
    task_id: str | None,
    response_payload: dict[str, object],
    **kwargs: object,
) -> None:
    try:
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type=task_type,
            biz_type=biz_type,
            status="success",
            task_id=task_id,
            response_payload=response_payload,
            **kwargs,
        )
        db.commit()
    except Exception:
        db.rollback()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 3})
def run_search_notes(
    self,
    keyword: str,
    sort: int = 1,
    auto_enrich: bool = True,
    trigger_comments: bool = False,
    max_items: int = 20,
    batch_id: str | None = None,
) -> dict:
    batch_id = batch_id or uuid.uuid4().hex[:16]
    db = _db()
    try:
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_search",
            biz_type="query",
            status="running",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={
                "keyword": keyword,
                "sort": sort,
                "auto_enrich": auto_enrich,
                "trigger_comments": trigger_comments,
                "max_items": max_items,
            },
            response_payload={"message": "search started"},
        )
        db.commit()

        response = client.search_notes(keyword=keyword, sort=sort)
        items = (response.get("data") or [])[:max_items]
        row_count = save_search_results(
            db,
            keyword=keyword,
            sort=sort,
            results=items,
            batch_id=batch_id,
            task_id=self.request.id,
        )

        db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET status = 'success',
                    task_id = :task_id,
                    row_count = :row_count,
                    response_payload = CAST(:response_payload AS jsonb),
                    completed_at = now(),
                    updated_at = now()
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "task_id": self.request.id,
                "row_count": row_count,
                "response_payload": json.dumps(response, ensure_ascii=False),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="note_search",
            biz_type="query",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={"keyword": keyword, "sort": sort},
            response_payload={"error": str(exc)},
        )
        raise
    finally:
        db.close()

    if auto_enrich:
        for idx, item in enumerate(items):
            note_id = str(item.get("noteId") or "").strip()
            if not note_id:
                continue
            note_countdown = max(0, settings.huitun_auto_note_info_spacing_seconds * idx)
            trigger_note_info.apply_async(args=[note_id], countdown=note_countdown)
            if trigger_comments:
                comment_countdown = max(0, settings.huitun_auto_note_comment_spacing_seconds * (idx + 1))
                trigger_note_comments.apply_async(args=[note_id], countdown=comment_countdown)

    return {"batch_id": batch_id, "count": len(items)}


@celery_app.task(bind=True, max_retries=3)
def run_search_anchors(
    self,
    keyword: str,
    max_items: int = 120,
    auto_enrich: bool = True,
) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    db = _db()
    summary: dict[str, object] = {"anchor_rows": 0, "updated_notes": 0, "author_ids": []}
    try:
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="anchor_search",
            biz_type="query",
            status="running",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={
                "keyword": keyword,
                "max_items": max_items,
                "auto_enrich": auto_enrich,
            },
            response_payload={"message": "anchor search started"},
        )
        db.commit()

        response = client.search_anchors(keyword=keyword)
        items = (response.get("data") or [])[: max(1, min(max_items, 300))]
        if not isinstance(items, list):
            items = []

        summary = save_anchor_search_results(
            db,
            keyword=keyword,
            results=items,
            batch_id=batch_id,
            task_id=self.request.id,
        )

        db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET status = 'success',
                    task_id = :task_id,
                    row_count = :row_count,
                    response_payload = CAST(:response_payload AS jsonb),
                    completed_at = now(),
                    updated_at = now()
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "task_id": self.request.id,
                "row_count": int(summary.get("anchor_rows") or 0),
                "response_payload": json.dumps(
                    {
                        "response": response,
                        "summary": {
                            "anchor_rows": summary.get("anchor_rows"),
                            "updated_notes": summary.get("updated_notes"),
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="anchor_search",
            biz_type="query",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={"keyword": keyword, "max_items": max_items},
            response_payload={"error": str(exc)},
        )
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()

    if auto_enrich:
        author_ids = list(dict.fromkeys(summary.get("author_ids") or []))
        for idx, author_id in enumerate(author_ids[: max(1, settings.search_author_backfill_limit)]):
            if not author_id:
                continue
            trigger_anchor_info.apply_async(
                args=[author_id],
                queue=settings.task_priority_queue,
                countdown=idx * 2,
            )

    return {
        "batch_id": batch_id,
        "keyword": keyword,
        "anchor_count": int(summary.get("anchor_rows") or 0),
        "updated_notes": int(summary.get("updated_notes") or 0),
    }


@celery_app.task(bind=True, max_retries=3)
def trigger_note_info(self, note_id: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/noteInfo/back")
    db = _db()
    try:
        if _is_huitun_quota_exhausted("note_info"):
            return _log_quota_skipped(
                db,
                batch_id=batch_id,
                task_type="note_info",
                note_id=note_id,
                task_id=self.request.id,
                back_url=back_url,
            )
        response = client.create_note_info(note_link=note_id, back_url=back_url)
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_info",
            biz_type="collect",
            status="running",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    except Exception as exc:
        db.rollback()
        if _is_task_limit_error(exc) or _is_quota_error(exc):
            _safe_log_skipped_success(
                db,
                batch_id=batch_id,
                task_type="note_info",
                biz_type="collect",
                note_id=note_id,
                task_id=self.request.id,
                request_payload={"note_id": note_id, "back_url": back_url},
                response_payload={
                    "skipped": True,
                    "reason": "quota_exhausted" if _is_quota_error(exc) else "provider_note_info_task_pool_saturated",
                    "error": str(exc),
                },
            )
            return {
                "batch_id": batch_id,
                "skipped": True,
                "reason": "quota_exhausted" if _is_quota_error(exc) else "provider_note_info_task_pool_saturated",
            }
        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="note_info",
            biz_type="collect",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def trigger_anchor_info(self, anchor_ref: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/anchorInfo/back")
    db = _db()
    try:
        author_id, anchor_link = _resolve_anchor_target(db, anchor_ref)
        request_anchor = anchor_link or anchor_ref
        response = client.create_anchor_info(anchor_link=request_anchor, back_url=back_url)
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="anchor_info",
            biz_type="collect",
            status="running",
            author_id=author_id,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "anchor_link": request_anchor, "back_url": back_url},
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    except Exception as exc:
        db.rollback()
        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="anchor_info",
            biz_type="collect",
            author_id=anchor_ref,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def trigger_fans_portrait(self, anchor_ref: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/fansProfile/back")
    db = _db()
    try:
        author_id, anchor_link = _resolve_anchor_target(db, anchor_ref)
        if not anchor_link:
            raise ValueError(f"anchor_link missing for fans_portrait: {anchor_ref}")

        response = client.create_fans_portrait(anchor_link=anchor_link, back_url=back_url)
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="fans_portrait",
            biz_type="collect",
            status="running",
            author_id=author_id,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "anchor_link": anchor_link, "back_url": back_url},
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    except Exception as exc:
        db.rollback()
        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="fans_portrait",
            biz_type="collect",
            author_id=anchor_ref,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def trigger_note_comments(self, note_id: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/noteComment/back")
    db = _db()
    try:
        if _is_huitun_quota_exhausted("note_comment"):
            return _log_quota_skipped(
                db,
                batch_id=batch_id,
                task_type="note_comment",
                note_id=note_id,
                task_id=self.request.id,
                back_url=back_url,
            )
        # Stop hammering provider when comment async task pool is saturated.
        if _recent_note_comment_limit_errors(db) >= 60:
            create_crawl_log(
                db,
                batch_id=batch_id,
                task_type="note_comment",
                biz_type="collect",
                status="success",
                note_id=note_id,
                task_id=self.request.id,
                request_payload={"note_id": note_id, "back_url": back_url},
                response_payload={
                    "skipped": True,
                    "reason": "provider_comment_task_pool_saturated",
                    "window_minutes": 20,
                },
            )
            db.commit()
            return {"batch_id": batch_id, "skipped": True}

        response = client.create_note_comments(note_link=note_id, back_url=back_url)
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_comment",
            biz_type="collect",
            status="running",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    except Exception as exc:
        db.rollback()
        if _is_task_limit_error(exc) or _is_quota_error(exc):
            _safe_log_skipped_success(
                db,
                batch_id=batch_id,
                task_type="note_comment",
                biz_type="collect",
                note_id=note_id,
                task_id=self.request.id,
                request_payload={"note_id": note_id, "back_url": back_url},
                response_payload={
                    "skipped": True,
                    "reason": "quota_exhausted" if _is_quota_error(exc) else "provider_comment_task_pool_saturated",
                    "error": str(exc),
                },
            )
            return {
                "batch_id": batch_id,
                "skipped": True,
                "reason": "quota_exhausted" if _is_quota_error(exc) else "provider_comment_task_pool_saturated",
            }

        _safe_log_failure(
            db,
            batch_id=batch_id,
            task_type="note_comment",
            biz_type="collect",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def trigger_search_backfill(
    self,
    job_id: str,
    query: str,
    sort: int = 1,
    max_items: int = 260,
    auto_enrich: bool = True,
    trigger_comments: bool = False,
) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    db = _db()
    try:
        mark_search_job_running(
            db,
            job_id=job_id,
            crawl_batch_id=batch_id,
            task_id=self.request.id,
        )
        task = run_search_notes.delay(
            batch_id=batch_id,
            keyword=query,
            sort=sort,
            auto_enrich=auto_enrich,
            trigger_comments=trigger_comments,
            max_items=max(1, min(max_items, 500)),
        )
        mark_search_job_running(
            db,
            job_id=job_id,
            crawl_batch_id=batch_id,
            task_id=task.id,
        )
        return {"job_id": job_id, "batch_id": batch_id, "task_id": task.id}
    except Exception as exc:
        db.rollback()
        mark_search_job_failed(db, job_id=job_id, error_msg=str(exc))
        if _is_retryable_error(exc) and self.request.retries < self.max_retries:
            _retry_later(self, exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def trigger_keyword_analysis(
    self,
    keyword: str,
    last_days: int,
    priority: int = 3,
    note_type: int | None = None,
    business: int | None = None,
    goods: int | None = None,
    max_note_num: int | None = None,
) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/keywordAnalysis/back")
    db = _db()
    try:
        response = client.create_keyword_analysis(
            keyword=keyword,
            last_days=last_days,
            priority=priority,
            note_type=note_type,
            business=business,
            goods=goods,
            max_note_num=max_note_num,
            back_url=back_url,
        )
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="keyword_analysis",
            biz_type="analysis",
            status="running",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={
                "keyword": keyword,
                "last_days": last_days,
                "priority": priority,
                "note_type": note_type,
                "business": business,
                "goods": goods,
                "max_note_num": max_note_num,
                "back_url": back_url,
            },
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    finally:
        db.close()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def trigger_brand_analysis(self, brand_name: str, priority: int = 3, last_days: int = 30) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/brandAnalysis/back")
    db = _db()
    try:
        response = client.create_brand_analysis(
            brand_name=brand_name,
            back_url=back_url,
            priority=priority,
            last_days=last_days,
        )
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="brand_analysis",
            biz_type="analysis",
            status="running",
            brand_name=brand_name,
            task_id=self.request.id,
            request_payload={
                "brand_name": brand_name,
                "priority": priority,
                "last_days": last_days,
                "back_url": back_url,
            },
            response_payload=response,
        )
        db.commit()
        return {"batch_id": batch_id, "response": response}
    finally:
        db.close()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_brand_info_and_accounts(self, brand_name: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    db = _db()
    try:
        info = client.get_brand_simple_info(brand_name=brand_name)
        accounts = client.get_brand_accounts(brand_name=brand_name)
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="brand_info_accounts",
            biz_type="query",
            status="success",
            brand_name=brand_name,
            task_id=self.request.id,
            request_payload={"brand_name": brand_name},
            response_payload={"info": info, "accounts": accounts},
        )

        upsert_brand_dim_and_accounts(
            db,
            brand_payload=info.get("data") if isinstance(info, dict) else {},
            accounts=(accounts.get("data") if isinstance(accounts, dict) else []) or [],
            batch_id=batch_id,
            task_id=self.request.id,
        )

        upsert_brand_accounts(
            db,
            brand_name=brand_name,
            accounts=(accounts.get("data") if isinstance(accounts, dict) else []) or [],
            batch_id=batch_id,
            task_id=self.request.id,
        )

        db.execute(
            text(
                """
                UPDATE xhs_crawl_log
                SET row_count = (
                    SELECT COUNT(*) FROM xhs_brand_account_rel WHERE brand_name = :brand_name
                ),
                completed_at = now(),
                updated_at = now()
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id, "brand_name": brand_name},
        )
        db.commit()
        return {"batch_id": batch_id, "info": info, "accounts": accounts}
    finally:
        db.close()
