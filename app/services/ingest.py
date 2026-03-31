from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.anchor_links import resolve_author_id


def _normalize_timestamp_seconds(ts: float) -> float:
    abs_ts = abs(ts)

    # 微秒级
    if abs_ts >= 1_000_000_000_000_000:
        return ts / 1_000_000

    # 毫秒级
    if abs_ts >= 1_000_000_000_000:
        return ts / 1_000

    # 秒级
    return ts


def _from_unix_timestamp(ts: float) -> datetime | None:
    try:
        normalized = _normalize_timestamp_seconds(ts)
        return datetime.fromtimestamp(normalized, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _as_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return _from_unix_timestamp(float(value))

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return _from_unix_timestamp(float(s))

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def _sort_label(sort_value: int | str | None) -> str:
    return "read_desc" if str(sort_value) == "1" else "publish_desc"


def _comment_hash(note_id: str, comment_text: str, sort_order: int | None) -> str:
    raw = f"{note_id}|{sort_order}|{comment_text.strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _canonical_note_url(note_id: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{note_id}"


def _lookup_author_id_by_anchor_link(db: Session, anchor_link: Any) -> str | None:
    if anchor_link in (None, ""):
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
        {"anchor_link": str(anchor_link).strip()},
    ).first()
    if not row:
        return None
    return str(row[0]).strip() or None


def _extract_note_id(value: Any) -> str | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None

    if "/" not in text and "?" not in text and len(text) <= 64:
        return text

    patterns = (
        r"/explore/([0-9a-zA-Z]+)",
        r"/discovery/item/([0-9a-zA-Z]+)",
        r"/notes/([0-9a-zA-Z]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    match = re.search(r"([0-9a-zA-Z]{16,32})", text)
    if match:
        return match.group(1)

    return text[:64]


def _to_int(value: Any) -> int:
    if value in (None, "", "null"):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_optional_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_optional_float(value: Any, *, divisor: float = 1.0) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value) / divisor
    except (TypeError, ValueError):
        return None


def _first_non_empty(payload: dict, *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _extract_list(payload: dict, *keys: str) -> list[dict]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for sub_key in ("list", "rows", "items", "data"):
                sub_value = value.get(sub_key)
                if isinstance(sub_value, list):
                    return sub_value
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for sub_key in keys:
            sub_value = data.get(sub_key)
            if isinstance(sub_value, list):
                return sub_value
        for sub_key in ("list", "rows", "items"):
            sub_value = data.get(sub_key)
            if isinstance(sub_value, list):
                return sub_value
    return []


def _normalize_text_list(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        items = [part.strip() for part in re.split(r"[,\n]+", value) if part.strip()]
        return items
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    return []


def _extract_media_urls(payload: dict) -> list[str]:
    urls: list[str] = []

    for key in ("mediaUrls", "media_urls", "imageUrls", "imgList", "imageList", "images"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    candidate = _first_non_empty(item, "url", "imageUrl", "imgUrl", "src")
                    if candidate:
                        urls.append(str(candidate).strip())

    single_url = _first_non_empty(payload, "imageUrl", "coverImageUrl", "cover", "coverUrl")
    if single_url:
        urls.insert(0, str(single_url).strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _sentiment_label(value: Any) -> str | None:
    mapping = {
        "1": "positive",
        "2": "neutral",
        "3": "negative",
        "4": "question",
    }
    if value in (None, ""):
        return None
    return mapping.get(str(value).strip())


def _build_distribution(labels: Any, values: Any) -> Any:
    label_items = _normalize_text_list(labels)

    if isinstance(values, list):
        value_items = values
    elif values in (None, ""):
        value_items = []
    else:
        value_items = [values]

    if label_items and value_items and len(label_items) == len(value_items):
        return [
            {"label": label, "value": value}
            for label, value in zip(label_items, value_items, strict=False)
        ]

    if label_items or value_items:
        return {"labels": label_items, "values": value_items}

    return {}


def insert_raw_payload(
    db: Session,
    table_name: str,
    payload: dict,
    task_type: str,
    batch_id: str | None = None,
    task_id: str | None = None,
    source_key: str | None = None,
) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO {table_name}(task_type, batch_id, task_id, source_key, payload)
            VALUES (:task_type, :batch_id, :task_id, :source_key, CAST(:payload AS jsonb))
            """
        ),
        {
            "task_type": task_type,
            "batch_id": batch_id,
            "task_id": task_id,
            "source_key": source_key,
            "payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def create_crawl_log(
    db: Session,
    *,
    batch_id: str,
    task_type: str,
    biz_type: str,
    status: str,
    keyword: str | None = None,
    note_id: str | None = None,
    author_id: str | None = None,
    brand_name: str | None = None,
    task_id: str | None = None,
    request_payload: dict | None = None,
    response_payload: dict | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO xhs_crawl_log(
                batch_id, task_type, biz_type, status, keyword, note_id, author_id,
                brand_name, task_id, request_payload, response_payload
            )
            VALUES (
                :batch_id, :task_type, :biz_type, :status, :keyword, :note_id, :author_id,
                :brand_name, :task_id, CAST(:request_payload AS jsonb), CAST(:response_payload AS jsonb)
            )
            ON CONFLICT (batch_id) DO UPDATE SET
                task_type = EXCLUDED.task_type,
                biz_type = EXCLUDED.biz_type,
                status = EXCLUDED.status,
                keyword = EXCLUDED.keyword,
                note_id = EXCLUDED.note_id,
                author_id = EXCLUDED.author_id,
                brand_name = EXCLUDED.brand_name,
                task_id = EXCLUDED.task_id,
                request_payload = EXCLUDED.request_payload,
                response_payload = EXCLUDED.response_payload,
                updated_at = now()
            """
        ),
        {
            "batch_id": batch_id,
            "task_type": task_type,
            "biz_type": biz_type,
            "status": status,
            "keyword": keyword,
            "note_id": note_id,
            "author_id": author_id,
            "brand_name": brand_name,
            "task_id": task_id,
            "request_payload": json.dumps(request_payload or {}, ensure_ascii=False),
            "response_payload": json.dumps(response_payload or {}, ensure_ascii=False),
        },
    )


def mark_task_callback(
    db: Session,
    batch_id: str,
    callback_payload: dict,
    row_count: int = 0,
    status: str = "success",
) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_crawl_log
            SET callback_payload = CAST(:callback_payload AS jsonb),
                row_count = :row_count,
                is_callback_received = true,
                status = :status,
                completed_at = now(),
                updated_at = now()
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "callback_payload": json.dumps(callback_payload, ensure_ascii=False),
            "row_count": row_count,
            "status": status,
        },
    )


def mark_task_success(
    db: Session,
    batch_id: str,
    row_count: int = 0,
    response_payload: dict | None = None,
) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_crawl_log
            SET status = 'success',
                row_count = :row_count,
                response_payload = COALESCE(CAST(:response_payload AS jsonb), response_payload),
                completed_at = now(),
                updated_at = now()
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "row_count": row_count,
            "response_payload": json.dumps(response_payload, ensure_ascii=False) if response_payload is not None else None,
        },
    )


def mark_task_error(db: Session, batch_id: str, error_msg: str) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_crawl_log
            SET status = 'failed',
                error_msg = :error_msg,
                retry_count = retry_count + 1,
                updated_at = now()
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id, "error_msg": error_msg[:1000]},
    )


def save_search_results(
    db: Session,
    *,
    keyword: str,
    sort: int,
    results: list[dict],
    batch_id: str,
    task_id: str | None,
) -> int:
    rows = 0
    sort_type = _sort_label(sort)
    _industry_matcher = None
    try:
        from app.services.industry_catalog import match_note_industries
        _industry_matcher = match_note_industries
    except Exception:
        _industry_matcher = None

    for idx, item in enumerate(results, start=1):
        note_id = str(item.get("noteId") or "").strip()
        if not note_id:
            continue

        publish_time = _as_dt(
            item.get("ts")
            or item.get("publishTime")
            or item.get("publish_time")
            or item.get("time")
        )
        media_type = _first_non_empty(item, "type", "mediaType")
        duration_seconds = _to_optional_int(_first_non_empty(item, "duration", "durationSeconds"))
        tags = _normalize_text_list(_first_non_empty(item, "topicList", "topic", "noteTag", "tags"))
        media_urls = _extract_media_urls(item)
        cover_image_url = _first_non_empty(item, "imageUrl", "coverImageUrl", "cover")
        author_id = str(
            _first_non_empty(item, "anchorId", "authorId", "author_id", "userId", "redId")
            or ""
        ).strip() or None
        author_fans_count = _to_optional_int(_first_non_empty(item, "fans", "fansCount"))
        like_count = _to_optional_int(_first_non_empty(item, "like", "likeCount"))
        comment_count = _to_optional_int(_first_non_empty(item, "comment", "commentCount", "comm"))
        collection_count = _to_optional_int(_first_non_empty(item, "collect", "collectCount", "collectionCount", "saveCount"))
        share_count = _to_optional_int(_first_non_empty(item, "share", "shareCount"))
        read_count = _to_optional_int(_first_non_empty(item, "read", "readCount"))
        stat_count = _to_optional_int(_first_non_empty(item, "stat", "statCount"))
        interaction_total = (
            _to_int(like_count)
            + _to_int(comment_count)
            + _to_int(collection_count)
            + _to_int(share_count)
        )
        ext_payload = {
            "source": "search_notes",
            "raw": item,
        }

        canonical_post_url = _canonical_note_url(note_id)
        search_content = _first_non_empty(item, "desc", "content", "noteContent")
        raw_brand_aliases = _normalize_text_list(_first_non_empty(item, "brand", "brandList", "brandName"))

        db.execute(
            text(
                """
                INSERT INTO xhs_note_search_result(
                    batch_id, task_id, keyword, sort_type, search_rank, note_id, title,
                    author_nickname, post_url, publish_time
                )
                VALUES(
                    :batch_id, :task_id, :keyword, :sort_type, :search_rank, :note_id, :title,
                    :author_nickname, :post_url, :publish_time
                )
                ON CONFLICT (keyword, sort_type, note_id, search_date) DO UPDATE SET
                    batch_id = EXCLUDED.batch_id,
                    task_id = EXCLUDED.task_id,
                    search_rank = EXCLUDED.search_rank,
                    title = EXCLUDED.title,
                    author_nickname = EXCLUDED.author_nickname,
                    post_url = EXCLUDED.post_url,
                    publish_time = EXCLUDED.publish_time,
                    created_at = now()
                """
            ),
            {
                "batch_id": batch_id,
                "task_id": task_id,
                "keyword": keyword,
                "sort_type": sort_type,
                "search_rank": idx,
                "note_id": note_id,
                "title": item.get("title"),
                "author_nickname": item.get("nick") or item.get("authorNickname"),
                "post_url": canonical_post_url,
                "publish_time": publish_time,
            },
        )

        db.execute(
            text(
                """
                INSERT INTO xhs_note_fact(
                    note_id, title, post_url, publish_time, media_type, duration_seconds,
                    tags, media_urls, cover_image_url, author_id, author_nickname, author_fans_count,
                    like_count, comment_count, collection_count, share_count, read_count, interaction_total, stat_count, ext_payload,
                    search_keyword, search_rank, search_type, batch_id, source_task_id
                )
                VALUES(
                    :note_id, :title, :post_url, :publish_time, :media_type, :duration_seconds,
                    :tags, CAST(:media_urls AS jsonb), :cover_image_url, :author_id, :author_nickname, :author_fans_count,
                    COALESCE(:like_count, 0), COALESCE(:comment_count, 0), COALESCE(:collection_count, 0), COALESCE(:share_count, 0), COALESCE(:read_count, 0),
                    COALESCE(:interaction_total, 0), COALESCE(:stat_count, 0), CAST(:ext_payload AS jsonb),
                    :search_keyword, :search_rank, :search_type, :batch_id, :source_task_id
                )
                ON CONFLICT (note_id) DO UPDATE SET
                    title = COALESCE(EXCLUDED.title, xhs_note_fact.title),
                    post_url = COALESCE(EXCLUDED.post_url, xhs_note_fact.post_url),
                    publish_time = COALESCE(EXCLUDED.publish_time, xhs_note_fact.publish_time),
                    media_type = COALESCE(EXCLUDED.media_type, xhs_note_fact.media_type),
                    duration_seconds = COALESCE(EXCLUDED.duration_seconds, xhs_note_fact.duration_seconds),
                    tags = CASE
                        WHEN array_length(EXCLUDED.tags, 1) > 0 THEN EXCLUDED.tags
                        ELSE xhs_note_fact.tags
                    END,
                    media_urls = COALESCE(EXCLUDED.media_urls, xhs_note_fact.media_urls),
                    cover_image_url = COALESCE(EXCLUDED.cover_image_url, xhs_note_fact.cover_image_url),
                    author_id = COALESCE(EXCLUDED.author_id, xhs_note_fact.author_id),
                    author_nickname = COALESCE(EXCLUDED.author_nickname, xhs_note_fact.author_nickname),
                    author_fans_count = COALESCE(EXCLUDED.author_fans_count, xhs_note_fact.author_fans_count),
                    like_count = CASE
                        WHEN :like_count IS NOT NULL THEN EXCLUDED.like_count
                        ELSE xhs_note_fact.like_count
                    END,
                    comment_count = CASE
                        WHEN :comment_count IS NOT NULL THEN EXCLUDED.comment_count
                        ELSE xhs_note_fact.comment_count
                    END,
                    collection_count = CASE
                        WHEN :collection_count IS NOT NULL THEN EXCLUDED.collection_count
                        ELSE xhs_note_fact.collection_count
                    END,
                    share_count = CASE
                        WHEN :share_count IS NOT NULL THEN EXCLUDED.share_count
                        ELSE xhs_note_fact.share_count
                    END,
                    read_count = CASE
                        WHEN :read_count IS NOT NULL THEN EXCLUDED.read_count
                        ELSE xhs_note_fact.read_count
                    END,
                    interaction_total = CASE
                        WHEN :interaction_total > 0 THEN EXCLUDED.interaction_total
                        ELSE xhs_note_fact.interaction_total
                    END,
                    stat_count = CASE
                        WHEN :stat_count IS NOT NULL THEN EXCLUDED.stat_count
                        ELSE xhs_note_fact.stat_count
                    END,
                    ext_payload = COALESCE(EXCLUDED.ext_payload, xhs_note_fact.ext_payload),
                    search_keyword = EXCLUDED.search_keyword,
                    search_rank = EXCLUDED.search_rank,
                    search_type = EXCLUDED.search_type,
                    batch_id = EXCLUDED.batch_id,
                    source_task_id = EXCLUDED.source_task_id,
                    updated_at = now()
                """
            ),
            {
                "note_id": note_id,
                "title": item.get("title"),
                "post_url": canonical_post_url,
                "publish_time": publish_time,
                "media_type": media_type,
                "duration_seconds": duration_seconds,
                "tags": tags,
                "media_urls": json.dumps(media_urls, ensure_ascii=False) if media_urls else None,
                "cover_image_url": cover_image_url or (media_urls[0] if media_urls else None),
                "author_id": author_id,
                "author_nickname": item.get("nick") or item.get("authorNickname"),
                "author_fans_count": author_fans_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "collection_count": collection_count,
                "share_count": share_count,
                "read_count": read_count,
                "interaction_total": interaction_total,
                "stat_count": stat_count,
                "ext_payload": json.dumps(ext_payload, ensure_ascii=False),
                "search_keyword": keyword,
                "search_rank": idx,
                "search_type": sort_type,
                "batch_id": batch_id,
                "source_task_id": task_id,
            },
        )
        if _industry_matcher:
            _industry_matcher(
                db,
                note_id=note_id,
                search_keyword=keyword,
                title=str(item.get("title") or ""),
                content=str(search_content or ""),
                tags=tags,
                brand_aliases=raw_brand_aliases,
            )
        rows += 1

    return rows


def upsert_note_detail(
    db: Session,
    payload: dict,
    *,
    batch_id: str | None = None,
    task_id: str | None = None,
) -> str | None:
    note_id = str(
        _extract_note_id(_first_non_empty(payload, "noteId", "note_id", "id", "noteLink"))
        or ""
    ).strip()
    if not note_id:
        return None

    title = _first_non_empty(payload, "title", "noteTitle")
    post_url = _canonical_note_url(note_id)
    publish_time = _as_dt(_first_non_empty(payload, "ts", "publishTime", "publish_time", "time", "createTime", "postTime"))
    content = _first_non_empty(payload, "desc", "content")
    media_type = _first_non_empty(payload, "type", "mediaType")
    duration_seconds = _to_optional_int(_first_non_empty(payload, "duration", "durationSeconds"))
    tags = _normalize_text_list(_first_non_empty(payload, "topicList", "topics", "tags", "topic"))
    media_urls = _extract_media_urls(payload)
    cover_image_url = _first_non_empty(payload, "coverImageUrl", "cover", "imageUrl")
    stat_count = _to_int(_first_non_empty(payload, "stat", "statCount", "interactionCount"))
    exp_count = _to_int(_first_non_empty(payload, "exp", "expCount", "exposureCount"))
    author_fans_count = _to_int(_first_non_empty(payload, "fans", "fansCount", "authorFansCount"))

    author_id = str(
        _first_non_empty(payload, "redId", "authorId", "author_id", "userId")
        or ""
    ).strip() or None
    author_nickname = _first_non_empty(payload, "nick", "authorNickname", "nickname", "userName")

    liked_count = _first_non_empty(payload, "likedCount", "likeCount", "likes", "like")
    collected_count = _first_non_empty(payload, "collectedCount", "collectCount", "favorites", "coll")
    comment_count = _first_non_empty(payload, "commentCount", "comments", "comm")
    share_count = _first_non_empty(payload, "shareCount", "shares", "share")
    view_count = _first_non_empty(payload, "viewCount", "readCount", "reads", "read")
    like_count_int = _to_int(liked_count)
    collection_count_int = _to_int(collected_count)
    comment_count_int = _to_int(comment_count)
    share_count_int = _to_int(share_count)
    read_count_int = _to_int(view_count)
    interaction_total = like_count_int + collection_count_int + comment_count_int + share_count_int
    ext_payload = {
        "source": "note_detail_callback",
        "raw": payload,
    }

    db.execute(
        text(
            """
            INSERT INTO xhs_note_fact(
                note_id, title, content, post_url, publish_time, media_type, duration_seconds,
                tags, media_urls, cover_image_url, author_id, author_nickname, author_fans_count,
                like_count, collection_count, comment_count, share_count, read_count, interaction_total, stat_count, exp_count, ext_payload,
                batch_id, source_task_id
            )
            VALUES(
                :note_id, :title, :content, :post_url, :publish_time, :media_type, :duration_seconds,
                :tags, CAST(:media_urls AS jsonb), :cover_image_url, :author_id, :author_nickname, :author_fans_count,
                :like_count, :collection_count, :comment_count, :share_count, :read_count, :interaction_total, :stat_count, :exp_count, CAST(:ext_payload AS jsonb),
                :batch_id, :source_task_id
            )
            ON CONFLICT (note_id) DO UPDATE SET
                title = COALESCE(EXCLUDED.title, xhs_note_fact.title),
                content = COALESCE(EXCLUDED.content, xhs_note_fact.content),
                post_url = COALESCE(EXCLUDED.post_url, xhs_note_fact.post_url),
                publish_time = COALESCE(EXCLUDED.publish_time, xhs_note_fact.publish_time),
                media_type = COALESCE(EXCLUDED.media_type, xhs_note_fact.media_type),
                duration_seconds = COALESCE(EXCLUDED.duration_seconds, xhs_note_fact.duration_seconds),
                tags = CASE
                    WHEN array_length(EXCLUDED.tags, 1) > 0 THEN EXCLUDED.tags
                    ELSE xhs_note_fact.tags
                END,
                media_urls = COALESCE(EXCLUDED.media_urls, xhs_note_fact.media_urls),
                cover_image_url = COALESCE(EXCLUDED.cover_image_url, xhs_note_fact.cover_image_url),
                author_id = COALESCE(EXCLUDED.author_id, xhs_note_fact.author_id),
                author_nickname = COALESCE(EXCLUDED.author_nickname, xhs_note_fact.author_nickname),
                author_fans_count = COALESCE(EXCLUDED.author_fans_count, xhs_note_fact.author_fans_count),
                like_count = COALESCE(EXCLUDED.like_count, xhs_note_fact.like_count),
                collection_count = COALESCE(EXCLUDED.collection_count, xhs_note_fact.collection_count),
                comment_count = COALESCE(EXCLUDED.comment_count, xhs_note_fact.comment_count),
                share_count = COALESCE(EXCLUDED.share_count, xhs_note_fact.share_count),
                read_count = COALESCE(EXCLUDED.read_count, xhs_note_fact.read_count),
                interaction_total = COALESCE(EXCLUDED.interaction_total, xhs_note_fact.interaction_total),
                stat_count = COALESCE(EXCLUDED.stat_count, xhs_note_fact.stat_count),
                exp_count = COALESCE(EXCLUDED.exp_count, xhs_note_fact.exp_count),
                ext_payload = COALESCE(EXCLUDED.ext_payload, xhs_note_fact.ext_payload),
                batch_id = COALESCE(EXCLUDED.batch_id, xhs_note_fact.batch_id),
                source_task_id = COALESCE(EXCLUDED.source_task_id, xhs_note_fact.source_task_id),
                updated_at = now()
            """
        ),
        {
            "note_id": note_id,
            "title": title,
            "content": content,
            "post_url": post_url,
            "publish_time": publish_time,
            "media_type": media_type,
            "duration_seconds": duration_seconds,
            "tags": tags,
            "media_urls": json.dumps(media_urls, ensure_ascii=False) if media_urls else None,
            "cover_image_url": cover_image_url or (media_urls[0] if media_urls else None),
            "author_id": author_id,
            "author_nickname": author_nickname,
            "author_fans_count": author_fans_count,
            "like_count": like_count_int,
            "collection_count": collection_count_int,
            "comment_count": comment_count_int,
            "share_count": share_count_int,
            "read_count": read_count_int,
            "interaction_total": interaction_total,
            "stat_count": stat_count,
            "exp_count": exp_count,
            "ext_payload": json.dumps(ext_payload, ensure_ascii=False),
            "batch_id": batch_id,
            "source_task_id": task_id,
        },
    )

    try:
        from app.services.industry_catalog import match_note_industries
        search_keyword_row = db.execute(
            text(
                """
                SELECT search_keyword
                FROM xhs_note_fact
                WHERE note_id = :note_id
                """
            ),
            {"note_id": note_id},
        ).first()
        search_keyword = str(search_keyword_row[0]).strip() if search_keyword_row and search_keyword_row[0] else None
        brand_alias_rows = db.execute(
            text(
                """
                SELECT brand_name
                FROM xhs_note_brand_rel
                WHERE note_id = :note_id
                """
            ),
            {"note_id": note_id},
        ).scalars().all()
        match_note_industries(
            db,
            note_id=note_id,
            search_keyword=search_keyword,
            title=title,
            content=content,
            tags=tags,
            brand_aliases=[str(item).strip() for item in brand_alias_rows if str(item).strip()],
        )
    except Exception:
        pass

    return note_id


def insert_comments(db: Session, payload: dict) -> int:
    note_id = str(
        _extract_note_id(_first_non_empty(payload, "noteId", "note_id"))
        or _extract_note_id(_first_non_empty(payload, "noteLink"))
        or ""
    ).strip()

    comments = _extract_list(payload, "comments", "comment", "commentList", "comms", "list", "rows", "items")
    if not comments and all(k in payload for k in ("content", "comment")):
        comments = [payload]

    rows = 0
    touched_note_ids: set[str] = set()
    for idx, item in enumerate(comments, start=1):
        comment_text = str(
            _first_non_empty(item, "content", "comment", "commentText", "text", "comm")
            or ""
        ).strip()
        if not comment_text:
            continue

        current_note_id = str(
            _extract_note_id(_first_non_empty(item, "noteId", "note_id"))
            or note_id
            or ""
        ).strip()
        if not current_note_id:
            continue
        touched_note_ids.add(current_note_id)

        sort_order = item.get("sort") or idx
        comment_hash = _comment_hash(
            current_note_id,
            comment_text,
            int(sort_order) if str(sort_order).isdigit() else idx,
        )

        author_id = str(
            _first_non_empty(item, "redId", "authorId", "userId", "user_id")
            or ""
        ).strip() or None
        author_nickname = _first_non_empty(item, "nick", "nickname", "userName")
        like_count = _first_non_empty(item, "likedCount", "likeCount", "likes", "like")
        comment_time = _as_dt(_first_non_empty(item, "ts", "time", "createTime", "commentTime", "postTime"))
        comment_sentiment = _sentiment_label(_first_non_empty(item, "sentiment", "commentSentiment"))

        db.execute(
            text(
                """
                INSERT INTO xhs_comment_fact(
                    parent_note_id, comment_hash, comment_text, sort_order,
                    commenter_id, commenter_nickname, comment_likes, comment_time, comment_sentiment
                )
                VALUES(
                    :parent_note_id, :comment_hash, :comment_text, :sort_order,
                    :commenter_id, :commenter_nickname, :comment_likes, :comment_time, :comment_sentiment
                )
                ON CONFLICT (parent_note_id, comment_hash) DO UPDATE SET
                    comment_text = EXCLUDED.comment_text,
                    sort_order = EXCLUDED.sort_order,
                    commenter_id = COALESCE(EXCLUDED.commenter_id, xhs_comment_fact.commenter_id),
                    commenter_nickname = COALESCE(EXCLUDED.commenter_nickname, xhs_comment_fact.commenter_nickname),
                    comment_likes = COALESCE(EXCLUDED.comment_likes, xhs_comment_fact.comment_likes),
                    comment_time = COALESCE(EXCLUDED.comment_time, xhs_comment_fact.comment_time),
                    comment_sentiment = COALESCE(EXCLUDED.comment_sentiment, xhs_comment_fact.comment_sentiment)
                """
            ),
            {
                "parent_note_id": current_note_id,
                "comment_hash": comment_hash,
                "comment_text": comment_text,
                "sort_order": sort_order,
                "commenter_id": author_id,
                "commenter_nickname": author_nickname,
                "comment_likes": _to_int(like_count),
                "comment_time": comment_time,
                "comment_sentiment": comment_sentiment,
            },
        )
        rows += 1

    if touched_note_ids:
        db.execute(
            text(
                """
                UPDATE xhs_note_fact f
                SET comment_count = GREATEST(
                        COALESCE(f.comment_count, 0),
                        COALESCE(sub.comment_rows, 0)
                    ),
                    interaction_total = COALESCE(f.like_count, 0)
                                     + GREATEST(COALESCE(f.comment_count, 0), COALESCE(sub.comment_rows, 0))
                                     + COALESCE(f.collection_count, 0)
                                     + COALESCE(f.share_count, 0),
                    updated_at = now()
                FROM (
                    SELECT parent_note_id, COUNT(*) AS comment_rows
                    FROM xhs_comment_fact
                    WHERE parent_note_id = ANY(:note_ids)
                    GROUP BY parent_note_id
                ) sub
                WHERE f.note_id = sub.parent_note_id
                """
            ),
            {"note_ids": list(touched_note_ids)},
        )

    return rows


def upsert_anchor_detail(
    db: Session,
    payload: dict,
    *,
    batch_id: str | None = None,
    task_id: str | None = None,
) -> str | None:
    author_id = str(
        _first_non_empty(payload, "anchorId", "authorId", "userId", "id", "redId")
        or ""
    ).strip()
    if not author_id:
        return None

    nickname = _first_non_empty(payload, "nick", "nickname", "name")
    home_url = _first_non_empty(payload, "anchorLink", "url", "homeUrl")
    follower_count = _first_non_empty(payload, "fansNum", "fansCount", "followerCount")
    following_count = _first_non_empty(payload, "followNum", "followCount", "followingCount")
    like_collect_count = _first_non_empty(payload, "likedCollectedNum", "likeCollectCount", "likeCollCount")
    note_count = _first_non_empty(payload, "noteNum", "noteCount", "totalNoteCount")
    desc_text = _first_non_empty(payload, "userText", "desc", "description", "intro")
    verified = _first_non_empty(payload, "verified", "verify", "verifyDesc", "auth", "type")
    home_url = _first_non_empty(payload, "anchorLink", "url", "homeUrl")
    red_id = _first_non_empty(payload, "redId", "readId")
    tag_list = _first_non_empty(payload, "tagList", "tags")
    if not isinstance(tag_list, list):
        tag_list = []

    db.execute(
        text(
            """
            INSERT INTO xhs_anchor_dim(
                author_id, anchor_link, red_id, nickname, verified_type, user_text,
                user_sex, age, fans_count, follow_count, fans_add_7, fans_add_30, fans_add_90,
                note_add_7, note_add_30, note_add_90, total_note_count, like_coll_count,
                picture_cpm, picture_cpe, picture_price, video_cpm, video_cpe, video_price,
                contact, tag_list
            )
            VALUES(
                :author_id, :anchor_link, :red_id, :nickname, :verified_type, :user_text,
                :user_sex, :age, :fans_count, :follow_count, :fans_add_7, :fans_add_30, :fans_add_90,
                :note_add_7, :note_add_30, :note_add_90, :total_note_count, :like_coll_count,
                :picture_cpm, :picture_cpe, :picture_price, :video_cpm, :video_cpe, :video_price,
                :contact, :tag_list
            )
            ON CONFLICT (author_id) DO UPDATE SET
                anchor_link = COALESCE(EXCLUDED.anchor_link, xhs_anchor_dim.anchor_link),
                red_id = COALESCE(EXCLUDED.red_id, xhs_anchor_dim.red_id),
                nickname = COALESCE(EXCLUDED.nickname, xhs_anchor_dim.nickname),
                verified_type = COALESCE(EXCLUDED.verified_type, xhs_anchor_dim.verified_type),
                user_text = COALESCE(EXCLUDED.user_text, xhs_anchor_dim.user_text),
                user_sex = COALESCE(EXCLUDED.user_sex, xhs_anchor_dim.user_sex),
                age = COALESCE(EXCLUDED.age, xhs_anchor_dim.age),
                fans_count = COALESCE(EXCLUDED.fans_count, xhs_anchor_dim.fans_count),
                follow_count = COALESCE(EXCLUDED.follow_count, xhs_anchor_dim.follow_count),
                fans_add_7 = COALESCE(EXCLUDED.fans_add_7, xhs_anchor_dim.fans_add_7),
                fans_add_30 = COALESCE(EXCLUDED.fans_add_30, xhs_anchor_dim.fans_add_30),
                fans_add_90 = COALESCE(EXCLUDED.fans_add_90, xhs_anchor_dim.fans_add_90),
                note_add_7 = COALESCE(EXCLUDED.note_add_7, xhs_anchor_dim.note_add_7),
                note_add_30 = COALESCE(EXCLUDED.note_add_30, xhs_anchor_dim.note_add_30),
                note_add_90 = COALESCE(EXCLUDED.note_add_90, xhs_anchor_dim.note_add_90),
                total_note_count = COALESCE(EXCLUDED.total_note_count, xhs_anchor_dim.total_note_count),
                like_coll_count = COALESCE(EXCLUDED.like_coll_count, xhs_anchor_dim.like_coll_count),
                picture_cpm = COALESCE(EXCLUDED.picture_cpm, xhs_anchor_dim.picture_cpm),
                picture_cpe = COALESCE(EXCLUDED.picture_cpe, xhs_anchor_dim.picture_cpe),
                picture_price = COALESCE(EXCLUDED.picture_price, xhs_anchor_dim.picture_price),
                video_cpm = COALESCE(EXCLUDED.video_cpm, xhs_anchor_dim.video_cpm),
                video_cpe = COALESCE(EXCLUDED.video_cpe, xhs_anchor_dim.video_cpe),
                video_price = COALESCE(EXCLUDED.video_price, xhs_anchor_dim.video_price),
                contact = COALESCE(EXCLUDED.contact, xhs_anchor_dim.contact),
                tag_list = CASE
                    WHEN array_length(EXCLUDED.tag_list, 1) > 0 THEN EXCLUDED.tag_list
                    ELSE xhs_anchor_dim.tag_list
                END,
                updated_at = now()
            """
        ),
        {
            "author_id": author_id,
            "anchor_link": home_url,
            "red_id": str(red_id).strip() if red_id is not None else None,
            "nickname": nickname,
            "verified_type": str(verified).strip() if verified not in (None, "") else None,
            "user_text": desc_text,
            "user_sex": _first_non_empty(payload, "userSex", "sex"),
            "age": _to_optional_int(_first_non_empty(payload, "age")),
            "fans_count": _to_int(follower_count),
            "follow_count": _to_int(following_count),
            "fans_add_7": _to_optional_int(_first_non_empty(payload, "fansAdd7")),
            "fans_add_30": _to_optional_int(_first_non_empty(payload, "fansAdd30")),
            "fans_add_90": _to_optional_int(_first_non_empty(payload, "fansAdd90")),
            "note_add_7": _to_optional_int(_first_non_empty(payload, "noteAdd7")),
            "note_add_30": _to_optional_int(_first_non_empty(payload, "noteAdd30")),
            "note_add_90": _to_optional_int(_first_non_empty(payload, "noteAdd90")),
            "total_note_count": _to_int(note_count),
            "like_coll_count": _to_int(like_collect_count),
            "picture_cpm": _to_optional_float(_first_non_empty(payload, "pictureCpm"), divisor=100),
            "picture_cpe": _to_optional_float(_first_non_empty(payload, "pictureCpe"), divisor=100),
            "picture_price": _to_optional_float(_first_non_empty(payload, "picturePrice")),
            "video_cpm": _to_optional_float(_first_non_empty(payload, "videoCpm"), divisor=100),
            "video_cpe": _to_optional_float(_first_non_empty(payload, "videoCpe"), divisor=100),
            "video_price": _to_optional_float(_first_non_empty(payload, "videoPrice")),
            "contact": str(_first_non_empty(payload, "contact") or "").strip() or None,
            "tag_list": tag_list,
        },
    )
    return author_id


def upsert_fans_profile(
    db: Session,
    payload: dict,
    *,
    batch_id: str | None = None,
    task_id: str | None = None,
) -> str | None:
    anchor_link = _first_non_empty(payload, "anchorLink", "url", "homeUrl")
    author_id = resolve_author_id(
        str(_first_non_empty(payload, "anchorId", "authorId", "userId", "id", "redId") or "").strip() or None,
        _lookup_author_id_by_anchor_link(db, anchor_link),
    )
    if not author_id:
        return None

    snapshot_time = _as_dt(_first_non_empty(payload, "ts", "time", "createTime")) or datetime.now(timezone.utc)
    fans_count = _to_int(_first_non_empty(payload, "fansNum", "fansCount", "followerCount"))
    gender_distribution = _build_distribution(
        _first_non_empty(payload, "GENDER_X", "genderXList"),
        _first_non_empty(payload, "genderList", "genderDistribution", "genderRate"),
    )
    age_distribution = _build_distribution(
        _first_non_empty(payload, "ageXList"),
        _first_non_empty(payload, "ageList", "ageDistribution", "ageRate"),
    )
    city_distribution = _build_distribution(
        _first_non_empty(payload, "cityXList"),
        _first_non_empty(payload, "cityList", "cityDistribution", "cityRate"),
    )
    province_distribution = _build_distribution(
        _first_non_empty(payload, "provinceXList"),
        _first_non_empty(payload, "provinceList", "provinceDistribution", "provinceRate"),
    )
    interest_distribution = _build_distribution(
        _first_non_empty(payload, "interestXList"),
        _first_non_empty(payload, "interestList", "interestDistribution", "interestRate"),
    )
    fans_active_day_distribution = _build_distribution(
        _first_non_empty(payload, "FANSAVTIVEDAY_X", "fansActivesXDay"),
        _first_non_empty(payload, "fansActivesDay", "fansActiveDayDistribution", "activeDayRate"),
    )
    fans_active_hour_distribution = _build_distribution(
        _first_non_empty(payload, "FANSAVTIVEDAY_X", "fansActivesXDay"),
        _first_non_empty(payload, "fansActivesDay", "fansActiveHourDistribution", "activeHourRate"),
    )
    fans_active_week_distribution = _build_distribution(
        _first_non_empty(payload, "FANSAVTIVEWEEK_X", "fansActivesXWeek"),
        _first_non_empty(payload, "fansActivesWeek", "fansActiveWeekDistribution", "activeWeekRate"),
    )

    db.execute(
        text(
            """
            INSERT INTO xhs_fans_profile_snapshot(
                author_id, anchor_link, fans_count, gender_distribution, age_distribution,
                city_distribution, province_distribution, interest_distribution,
                fans_active_day_distribution, fans_active_hour_distribution,
                fans_active_week_distribution, snapshot_at
            )
            VALUES(
                :author_id, :anchor_link, :fans_count, CAST(:gender_distribution AS jsonb), CAST(:age_distribution AS jsonb),
                CAST(:city_distribution AS jsonb), CAST(:province_distribution AS jsonb), CAST(:interest_distribution AS jsonb),
                CAST(:fans_active_day_distribution AS jsonb), CAST(:fans_active_hour_distribution AS jsonb),
                CAST(:fans_active_week_distribution AS jsonb), :snapshot_at
            )
            """
        ),
        {
            "author_id": author_id,
            "anchor_link": anchor_link,
            "fans_count": fans_count,
            "gender_distribution": json.dumps(gender_distribution or {}, ensure_ascii=False),
            "age_distribution": json.dumps(age_distribution or {}, ensure_ascii=False),
            "city_distribution": json.dumps(city_distribution or {}, ensure_ascii=False),
            "province_distribution": json.dumps(province_distribution or {}, ensure_ascii=False),
            "interest_distribution": json.dumps(interest_distribution or {}, ensure_ascii=False),
            "fans_active_day_distribution": json.dumps(fans_active_day_distribution or {}, ensure_ascii=False),
            "fans_active_hour_distribution": json.dumps(fans_active_hour_distribution or {}, ensure_ascii=False),
            "fans_active_week_distribution": json.dumps(fans_active_week_distribution or {}, ensure_ascii=False),
            "snapshot_at": snapshot_time,
        },
    )
    db.execute(
        text(
            """
            UPDATE xhs_anchor_dim
            SET anchor_link = COALESCE(:anchor_link, anchor_link),
                fans_count = COALESCE(:fans_count, fans_count),
                gender_distribution = CAST(:gender_distribution AS jsonb),
                age_distribution = CAST(:age_distribution AS jsonb),
                city_distribution = CAST(:city_distribution AS jsonb),
                province_distribution = CAST(:province_distribution AS jsonb),
                interest_distribution = CAST(:interest_distribution AS jsonb),
                fans_active_day_distribution = CAST(:fans_active_day_distribution AS jsonb),
                fans_active_hour_distribution = CAST(:fans_active_hour_distribution AS jsonb),
                fans_active_week_distribution = CAST(:fans_active_week_distribution AS jsonb),
                updated_at = now()
            WHERE author_id = :author_id
            """
        ),
        {
            "author_id": author_id,
            "anchor_link": anchor_link,
            "fans_count": fans_count,
            "gender_distribution": json.dumps(gender_distribution or {}, ensure_ascii=False),
            "age_distribution": json.dumps(age_distribution or {}, ensure_ascii=False),
            "city_distribution": json.dumps(city_distribution or {}, ensure_ascii=False),
            "province_distribution": json.dumps(province_distribution or {}, ensure_ascii=False),
            "interest_distribution": json.dumps(interest_distribution or {}, ensure_ascii=False),
            "fans_active_day_distribution": json.dumps(fans_active_day_distribution or {}, ensure_ascii=False),
            "fans_active_hour_distribution": json.dumps(fans_active_hour_distribution or {}, ensure_ascii=False),
            "fans_active_week_distribution": json.dumps(fans_active_week_distribution or {}, ensure_ascii=False),
        },
    )
    return author_id


def upsert_keyword_analysis(db: Session, payload: dict) -> int:
    keyword = str(_first_non_empty(payload, "keyword") or "").strip()
    rows = _extract_list(payload, "list", "rows", "items", "analysisList")

    if rows:
        inserted = 0
        for idx, item in enumerate(rows, start=1):
            metric_name = _first_non_empty(item, "name", "metricName", "label", "title")
            metric_value = _first_non_empty(item, "value", "metricValue", "count", "ratio")
            db.execute(
                text(
                    """
                    INSERT INTO xhs_keyword_analysis(
                        keyword, row_no, metric_name, metric_value, source_payload
                    )
                    VALUES(
                        :keyword, :row_no, :metric_name, :metric_value, CAST(:source_payload AS jsonb)
                    )
                    """
                ),
                {
                    "keyword": keyword,
                    "row_no": idx,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "source_payload": json.dumps(item, ensure_ascii=False),
                },
            )
            inserted += 1
        return inserted

    db.execute(
        text(
            """
            INSERT INTO xhs_keyword_analysis(
                keyword, row_no, metric_name, metric_value, source_payload
            )
            VALUES(
                :keyword, 1, :metric_name, :metric_value, CAST(:source_payload AS jsonb)
            )
            """
        ),
        {
            "keyword": keyword,
            "metric_name": "raw_payload",
            "metric_value": None,
            "source_payload": json.dumps(payload, ensure_ascii=False),
        },
    )
    return 1


def upsert_brand_analysis(db: Session, payload: dict) -> int:
    brand_name = str(_first_non_empty(payload, "brandName", "keyword", "brand") or "").strip()
    snapshot_time = _as_dt(_first_non_empty(payload, "ts", "time", "createTime")) or datetime.now(timezone.utc)

    db.execute(
        text(
            """
            INSERT INTO xhs_brand_analysis_snapshot(
                brand_name, snapshot_time, source_payload
            )
            VALUES(
                :brand_name, :snapshot_time, CAST(:source_payload AS jsonb)
            )
            """
        ),
        {
            "brand_name": brand_name,
            "snapshot_time": snapshot_time,
            "source_payload": json.dumps(payload, ensure_ascii=False),
        },
    )
    return 1


def upsert_brand_accounts(
    db: Session,
    *,
    brand_id: str | None = None,
    brand_name: str | None = None,
    accounts: list[dict] | None = None,
    accounts_response: dict | None = None,
    batch_id: str | None = None,
    task_id: str | None = None,
) -> int:
    if accounts is None:
        accounts = _extract_list(accounts_response or {}, "list", "rows", "items", "data")

    if not accounts:
        return 0

    rows = 0
    for item in accounts:
        account_id = str(
            _first_non_empty(item, "accountId", "anchorId", "userId", "id", "redId")
            or ""
        ).strip()
        if not account_id:
            continue

        nickname = _first_non_empty(item, "nickname", "nick", "name")
        home_url = _first_non_empty(item, "homeUrl", "url", "anchorLink")

        db.execute(
            text(
                """
                INSERT INTO xhs_brand_account_rel(
                    brand_id,
                    brand_name,
                    account_id,
                    account_nickname,
                    home_url,
                    batch_id,
                    task_id,
                    source_payload
                )
                VALUES(
                    :brand_id,
                    :brand_name,
                    :account_id,
                    :account_nickname,
                    :home_url,
                    :batch_id,
                    :task_id,
                    CAST(:source_payload AS jsonb)
                )
                ON CONFLICT (brand_name, account_id) DO UPDATE SET
                    brand_id = COALESCE(EXCLUDED.brand_id, xhs_brand_account_rel.brand_id),
                    account_nickname = COALESCE(EXCLUDED.account_nickname, xhs_brand_account_rel.account_nickname),
                    home_url = COALESCE(EXCLUDED.home_url, xhs_brand_account_rel.home_url),
                    batch_id = EXCLUDED.batch_id,
                    task_id = EXCLUDED.task_id,
                    source_payload = EXCLUDED.source_payload,
                    updated_at = now()
                """
            ),
            {
                "brand_id": brand_id,
                "brand_name": brand_name,
                "account_id": account_id,
                "account_nickname": nickname,
                "home_url": home_url,
                "batch_id": batch_id,
                "task_id": task_id,
                "source_payload": json.dumps(item, ensure_ascii=False),
            },
        )
        rows += 1

    return rows


def upsert_brand_dim_and_accounts(
    db: Session,
    *,
    brand_payload: dict | None = None,
    accounts: list[dict] | None = None,
    brand_name: str | None = None,
    info_response: dict | None = None,
    batch_id: str | None = None,
    task_id: str | None = None,
) -> int:
    if brand_payload is None:
        brand_payload = info_response or {}

    if not brand_name:
        brand_name = (
            str(_first_non_empty(brand_payload, "brandName", "name", "brand") or "").strip()
            or None
        )

    brand_id = str(
        _first_non_empty(brand_payload, "brandId", "id")
        or ""
    ).strip() or None

    if brand_name:
        db.execute(
            text(
                """
                INSERT INTO xhs_brand_dim(
                    brand_id,
                    brand_name,
                    source_payload,
                    batch_id,
                    task_id
                )
                VALUES(
                    :brand_id,
                    :brand_name,
                    CAST(:source_payload AS jsonb),
                    :batch_id,
                    :task_id
                )
                ON CONFLICT (brand_name) DO UPDATE SET
                    brand_id = COALESCE(EXCLUDED.brand_id, xhs_brand_dim.brand_id),
                    source_payload = EXCLUDED.source_payload,
                    batch_id = EXCLUDED.batch_id,
                    task_id = EXCLUDED.task_id,
                    updated_at = now()
                """
            ),
            {
                "brand_id": brand_id,
                "brand_name": brand_name,
                "source_payload": json.dumps(brand_payload, ensure_ascii=False),
                "batch_id": batch_id,
                "task_id": task_id,
            },
        )

    return upsert_brand_accounts(
        db,
        brand_id=brand_id,
        brand_name=brand_name,
        accounts=accounts,
        batch_id=batch_id,
        task_id=task_id,
    )
