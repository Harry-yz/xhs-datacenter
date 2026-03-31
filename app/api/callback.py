from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.services.ingest import (
    _extract_note_id,
    insert_comments,
    insert_raw_payload,
    mark_task_callback,
    upsert_anchor_detail,
    upsert_brand_analysis,
    upsert_fans_profile,
    upsert_keyword_analysis,
    upsert_note_detail,
)
from app.schemas import APIResponse
from app.tasks.jobs import trigger_anchor_info, trigger_fans_portrait

router = APIRouter(prefix="/callback", tags=["callback"])
settings = get_settings()


def _find_batch_id(payload: dict) -> str | None:
    return payload.get("batch_id") or payload.get("batchId") or payload.get("taskId") or payload.get("task_id")


def _find_task_id(payload: dict) -> str | None:
    return payload.get("taskId") or payload.get("task_id")


def _resolve_batch_id(
    db: Session,
    *,
    payload: dict,
    task_type: str,
    note_id: str | None = None,
    author_id: str | None = None,
    anchor_link: str | None = None,
) -> str | None:
    raw_batch_id = _find_batch_id(payload)
    if raw_batch_id:
        row = db.execute(
            text("SELECT batch_id FROM xhs_crawl_log WHERE batch_id = :batch_id"),
            {"batch_id": raw_batch_id},
        ).first()
        if row:
            return str(raw_batch_id)

    if note_id:
        row = db.execute(
            text(
                """
                SELECT batch_id
                FROM xhs_crawl_log
                WHERE task_type = :task_type
                  AND note_id = :note_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"task_type": task_type, "note_id": note_id},
        ).first()
        if row:
            return str(row[0])

    if author_id:
        row = db.execute(
            text(
                """
                SELECT batch_id
                FROM xhs_crawl_log
                WHERE task_type = :task_type
                  AND author_id = :author_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"task_type": task_type, "author_id": author_id},
        ).first()
        if row:
            return str(row[0])

    if anchor_link:
        row = db.execute(
            text(
                """
                SELECT batch_id
                FROM xhs_crawl_log
                WHERE task_type = :task_type
                  AND request_payload->>'anchor_link' = :anchor_link
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"task_type": task_type, "anchor_link": anchor_link},
        ).first()
        if row:
            return str(row[0])

    return None


def _has_recent_collect_task(
    db: Session,
    *,
    task_type: str,
    hours: int,
    author_id: str | None = None,
) -> bool:
    if not author_id:
        return False

    row = db.execute(
        text(
            """
            SELECT 1
            FROM xhs_crawl_log
            WHERE task_type = :task_type
              AND author_id = :author_id
              AND created_at >= now() - (:hours || ' hour')::interval
            LIMIT 1
            """
        ),
        {"task_type": task_type, "author_id": author_id, "hours": hours},
    ).first()
    return row is not None


def _is_valid_anchor_id(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    if len(value) < 16:
        return False
    if "/" in value or " " in value:
        return False
    return True


def _find_author_id_by_anchor_link(db: Session, anchor_link: str | None) -> str | None:
    if not anchor_link:
        return None
    row = db.execute(
        text(
            """
            SELECT author_id
            FROM xhs_anchor_dim
            WHERE anchor_link = :anchor_link
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"anchor_link": anchor_link},
    ).first()
    if not row:
        row = db.execute(
            text(
                """
                SELECT author_id
                FROM xhs_crawl_log
                WHERE author_id IS NOT NULL
                  AND author_id <> ''
                  AND request_payload->>'anchor_link' = :anchor_link
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"anchor_link": anchor_link},
        ).first()
        if not row:
            return None
    return str(row[0]).strip() or None


@router.post("/note", response_model=APIResponse)
async def note_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    task_id = _find_task_id(payload)
    note_id = str(_extract_note_id(payload.get("noteId") or payload.get("noteLink")) or "")
    batch_id = _resolve_batch_id(db, payload=payload, task_type="note_info", note_id=note_id or None)
    insert_raw_payload(db, "ods_note_raw", payload, task_type="note_info", batch_id=batch_id, task_id=task_id, source_key=note_id)
    upsert_note_detail(db, payload, batch_id=batch_id, task_id=task_id)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=1, status="success")
        db.commit()
    # 回调里只有昵称没有 author_id，这里只能尝试用昵称触发达人抓取需要你后续补映射规则
    author_hint = payload.get("nick")
    if author_hint:
        pass
    return APIResponse(data={"note_id": note_id})


@router.post("/anchor", response_model=APIResponse)
async def anchor_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    task_id = _find_task_id(payload)
    source_key = str(payload.get("anchorLink") or payload.get("anchorId") or payload.get("authorId") or payload.get("userId") or payload.get("redId") or "")
    author_hint = str(payload.get("anchorId") or payload.get("authorId") or payload.get("userId") or payload.get("redId") or "").strip() or None
    batch_id = _resolve_batch_id(db, payload=payload, task_type="anchor_info", author_id=author_hint)
    insert_raw_payload(db, "ods_anchor_raw", payload, task_type="anchor_info", batch_id=batch_id, task_id=task_id, source_key=source_key)
    author_id = upsert_anchor_detail(db, payload, batch_id=batch_id, task_id=task_id)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=1, status="success")
        db.commit()
    if (
        _is_valid_anchor_id(author_id)
        and not _has_recent_collect_task(db, task_type="fans_portrait", author_id=author_id, hours=168)
    ):
        trigger_fans_portrait.apply_async(args=[author_id], countdown=settings.huitun_task_retry_delay_seconds)
    return APIResponse(data={"author_id": author_id})


@router.post("/fans", response_model=APIResponse)
async def fans_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    task_id = _find_task_id(payload)
    anchor_link = str(payload.get("anchorLink") or payload.get("url") or payload.get("homeUrl") or "").strip() or None
    source_key = str(anchor_link or "")
    author_hint = str(payload.get("anchorId") or payload.get("authorId") or payload.get("userId") or payload.get("redId") or "").strip() or None
    if not author_hint:
        author_hint = _find_author_id_by_anchor_link(db, anchor_link)
    batch_id = _resolve_batch_id(
        db,
        payload=payload,
        task_type="fans_portrait",
        author_id=author_hint,
        anchor_link=anchor_link,
    )
    insert_raw_payload(db, "ods_fans_raw", payload, task_type="fans_portrait", batch_id=batch_id, task_id=task_id, source_key=source_key)
    author_id = upsert_fans_profile(db, payload, batch_id=batch_id, task_id=task_id)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=1, status="success")
        db.commit()
    return APIResponse(data={"author_id": author_id})


@router.post("/comment", response_model=APIResponse)
async def comment_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    task_id = _find_task_id(payload)
    source_key = str(_extract_note_id(payload.get("noteId") or payload.get("noteLink")) or payload.get("noteLink") or "")
    note_id = str(_extract_note_id(payload.get("noteId") or payload.get("noteLink")) or "").strip() or None
    batch_id = _resolve_batch_id(db, payload=payload, task_type="note_comment", note_id=note_id)
    insert_raw_payload(db, "ods_comment_raw", payload, task_type="note_comment", batch_id=batch_id, task_id=task_id, source_key=source_key)
    row_count = insert_comments(db, payload)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=row_count, status="success")
        db.commit()
    return APIResponse(data={"row_count": row_count})


@router.post("/keyword", response_model=APIResponse)
async def keyword_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    batch_id = _find_batch_id(payload)
    task_id = _find_task_id(payload)
    source_key = str(payload.get("keyword") or "")
    insert_raw_payload(db, "ods_keyword_raw", payload, task_type="keyword_analysis", batch_id=batch_id, task_id=task_id, source_key=source_key)
    row_count = upsert_keyword_analysis(db, payload)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=row_count, status="success")
        db.commit()
    return APIResponse(data={"row_count": row_count})


@router.post("/brand", response_model=APIResponse)
async def brand_callback(request: Request, db: Session = Depends(get_db)) -> APIResponse:
    payload = await request.json()
    batch_id = _find_batch_id(payload)
    task_id = _find_task_id(payload)
    source_key = str(payload.get("brandName") or payload.get("keyword") or "")
    insert_raw_payload(db, "ods_brand_raw", payload, task_type="brand_analysis", batch_id=batch_id, task_id=task_id, source_key=source_key)
    row_count = upsert_brand_analysis(db, payload)
    db.commit()
    if batch_id:
        mark_task_callback(db, batch_id=batch_id, callback_payload=payload, row_count=row_count, status="success")
        db.commit()
    return APIResponse(data={"row_count": row_count})
