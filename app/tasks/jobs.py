from __future__ import annotations

import json
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
    save_search_results,
    upsert_brand_accounts,
    upsert_brand_dim_and_accounts,
)
from app.services.search_center import mark_search_job_failed, mark_search_job_running
from app.tasks.celery_app import celery_app

settings = get_settings()
client = HuitunClient()


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


def _retry_later(task, exc: Exception):
    base_delay = settings.huitun_task_retry_delay_seconds
    if _is_task_limit_error(exc):
        # Task-pool saturation needs a longer cooldown; short retries only amplify failures.
        base_delay = max(base_delay, 1800)
    countdown = base_delay * (task.request.retries + 1)
    raise task.retry(exc=exc, countdown=countdown, max_retries=3)


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
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_search",
            biz_type="query",
            status="failed",
            keyword=keyword,
            task_id=self.request.id,
            request_payload={"keyword": keyword, "sort": sort},
            response_payload={"error": str(exc)},
        )
        db.commit()
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
def trigger_note_info(self, note_id: str) -> dict:
    batch_id = uuid.uuid4().hex[:16]
    back_url = _callback_url("/test/noteInfo/back")
    db = _db()
    try:
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
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_info",
            biz_type="collect",
            status="failed",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        db.commit()
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
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="anchor_info",
            biz_type="collect",
            status="failed",
            author_id=anchor_ref,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        db.commit()
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
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="fans_portrait",
            biz_type="collect",
            status="failed",
            author_id=anchor_ref,
            task_id=self.request.id,
            request_payload={"anchor_ref": anchor_ref, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        db.commit()
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
        create_crawl_log(
            db,
            batch_id=batch_id,
            task_type="note_comment",
            biz_type="collect",
            status="failed",
            note_id=note_id,
            task_id=self.request.id,
            request_payload={"note_id": note_id, "back_url": back_url},
            response_payload={"error": str(exc)},
        )
        db.commit()
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
    trigger_comments: bool = True,
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
