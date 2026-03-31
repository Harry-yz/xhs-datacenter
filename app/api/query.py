from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.beauty_catalog import load_beauty_catalog
from app.services.industry_catalog import sync_industry_catalog
from app.schemas import APIResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/beauty-taxonomy", response_model=APIResponse)
def get_beauty_taxonomy(db: Session = Depends(get_db)) -> APIResponse:
    return APIResponse(data=load_beauty_catalog(db))


@router.get("/industries", response_model=APIResponse)
def get_industries(db: Session = Depends(get_db)) -> APIResponse:
    sync_industry_catalog(db)
    rows = db.execute(
        text(
            """
            SELECT industry_key, industry_name, sort_no, keyword_count, status, updated_at
            FROM xhs_industry_dim
            ORDER BY sort_no ASC, industry_name ASC
            """
        )
    ).mappings().all()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        items.append(item)
    return APIResponse(data={"items": items})


@router.get("/categories", response_model=APIResponse)
def get_categories(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT tag AS name, COUNT(*) AS count
            FROM (
                SELECT jsonb_array_elements_text(to_jsonb(tags)) AS tag
                FROM xhs_note_fact
                WHERE tags IS NOT NULL AND array_length(tags, 1) > 0
            ) t
            GROUP BY tag
            ORDER BY COUNT(*) DESC, tag ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return APIResponse(data=[dict(row) for row in rows])


@router.get("/notes", response_model=APIResponse)
def get_notes(
    category: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="publish_time", pattern="^(publish_time|read_count|like_count|comment_count)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> APIResponse:
    offset = (page - 1) * size
    total = db.execute(
        text("SELECT COUNT(*) FROM xhs_note_fact WHERE :category = ANY(tags)"),
        {"category": category},
    ).scalar_one()
    sql = text(
        f"""
        SELECT note_id, title, author_id, author_nickname, read_count, like_count, comment_count,
               collection_count, share_count,
               'https://www.xiaohongshu.com/explore/' || note_id AS post_url,
               publish_time, tags
        FROM xhs_note_fact
        WHERE :category = ANY(tags)
        ORDER BY {sort_by} {order}
        LIMIT :size OFFSET :offset
        """
    )
    rows = db.execute(sql, {"category": category, "size": size, "offset": offset}).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        if item.get("publish_time"):
            item["publish_time"] = item["publish_time"].isoformat()
        item["tags"] = item.get("tags") or []
        items.append(item)
    return APIResponse(
        data={
            "list": items,
            "pagination": {
                "total": total,
                "page": page,
                "size": size,
                "has_more": offset + len(items) < total,
            },
        }
    )


@router.get("/notes/{note_id}", response_model=APIResponse)
def get_note_detail(note_id: str, db: Session = Depends(get_db)) -> APIResponse:
    row = db.execute(
        text(
            """
            SELECT note_id, title, content,
                   'https://www.xiaohongshu.com/explore/' || note_id AS post_url,
                   publish_time, media_type, duration_seconds,
                   tags, media_urls, cover_image_url, read_count, like_count, comment_count,
                   collection_count, share_count, stat_count, exp_count,
                   author_id, author_nickname, author_fans_count
            FROM xhs_note_fact WHERE note_id = :note_id
            """
        ),
        {"note_id": note_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="note not found")
    data = dict(row)
    if data.get("publish_time"):
        data["publish_time"] = data["publish_time"].isoformat()
    data["tags"] = data.get("tags") or []
    return APIResponse(data=data)


@router.get("/xhs-note-center", response_model=APIResponse)
def get_xhs_note_center(
    limit: int = Query(default=100, ge=1, le=1000),
    min_like: int = Query(default=0, ge=0),
    brand_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> APIResponse:
    brand_filter = brand_name or ""
    rows = db.execute(
        text(
            """
            SELECT v.*
            FROM xhs_note_center_view v
            WHERE v.like_count >= :min_like
              AND (
                    :brand_name = ''
                 OR EXISTS (
                        SELECT 1
                        FROM xhs_note_brand_rel rel
                        WHERE rel.note_id = v.note_id
                          AND rel.brand_name = :brand_name
                    )
              )
            ORDER BY like_count DESC, collection_count DESC, publish_time DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"limit": limit, "min_like": min_like, "brand_name": brand_filter},
    ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        for key in ("publish_time", "crawl_time"):
            if item.get(key):
                item[key] = item[key].isoformat()
        item["tags"] = item.get("tags") or []
        items.append(item)
    return APIResponse(data={"items": items})


@router.get("/xhs-brand-center", response_model=APIResponse)
def get_xhs_brand_center(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT *
            FROM xhs_brand_center_view
            ORDER BY note_count DESC, like_total DESC, brand_name ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        for key in ("latest_publish_time", "crawl_time"):
            if item.get(key):
                item[key] = item[key].isoformat()
        items.append(item)
    return APIResponse(data={"items": items})


@router.get("/xhs-comment-center", response_model=APIResponse)
def get_xhs_comment_center(
    limit: int = Query(default=100, ge=1, le=1000),
    note_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> APIResponse:
    note_id_filter = note_id or ""
    rows = db.execute(
        text(
            """
            SELECT *
            FROM xhs_comment_center_view
            WHERE (:note_id = '' OR parent_note_id = :note_id)
            ORDER BY crawl_time DESC
            LIMIT :limit
            """
        ),
        {"limit": limit, "note_id": note_id_filter},
    ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        for key in ("comment_time", "crawl_time"):
            if item.get(key):
                item[key] = item[key].isoformat()
        items.append(item)
    return APIResponse(data={"items": items})


@router.get("/xhs-anchor-center", response_model=APIResponse)
def get_xhs_anchor_center(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> APIResponse:
    rows = db.execute(
        text(
            """
            SELECT *
            FROM xhs_anchor_center_view
            ORDER BY follower_count DESC NULLS LAST, crawl_time DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        if item.get("crawl_time"):
            item["crawl_time"] = item["crawl_time"].isoformat()
        items.append(item)
    return APIResponse(data={"items": items})


@router.get("/tasks/{batch_id}", response_model=APIResponse)
def get_task(batch_id: str, db: Session = Depends(get_db)) -> APIResponse:
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
