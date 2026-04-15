from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.industry_catalog import ensure_industry_tables, resolve_industry_key
from app.services.search_intent import split_intent_terms

SearchType = Literal["influencer", "brand_category"]
SearchStatus = Literal["pending", "running", "ready", "failed"]

CategorySortKey = Literal["stat", "like", "read", "comments"]
CreatorSortKey = Literal["relevance", "followers", "notes", "sumStat"]
SortOrder = Literal["asc", "desc"]

_search_bootstrap_done = False
_incremental_refresh_last_at: float = 0.0
settings = get_settings()
_SEARCH_BOOTSTRAP_LOCK_KEY = 2026040201
_SEARCH_BOOTSTRAP_LOCK_TIMEOUT_MS = 500

@dataclass(frozen=True)
class IntentSplitResult:
    original: str
    intents: list[str]
    stopwords_removed: list[str]


@dataclass(frozen=True)
class SearchPlan:
    filters: dict[str, Any]
    sort: dict[str, str]
    limit: int
    sql_params: dict[str, Any]


@dataclass(frozen=True)
class FetchDecision:
    need_fetch: bool
    reasons: list[str]
    health: dict[str, Any]


def _safe_ddl(db: Session, ddl: str, *, ignore_permission: bool = False) -> None:
    try:
        db.execute(text(ddl))
    except Exception as exc:
        message = str(exc).lower()
        if (
            "pg_type_typname_nsp_index" in message
            or "already exists" in message
            or "duplicate key value violates unique constraint" in message
            or ("gin_trgm_ops" in message and "does not exist" in message)
        ):
            db.rollback()
            return
        if ignore_permission and ("permission denied" in message or "must be superuser" in message):
            db.rollback()
            return
        raise


def _search_schema_ready(db: Session) -> bool:
    row = db.execute(
        text(
            """
            SELECT
                to_regclass('public.xhs_search_job') IS NOT NULL AS has_search_job,
                to_regclass('public.xhs_search_synonym_dim') IS NOT NULL AS has_synonym_dim,
                to_regclass('public.xhs_note_term_rel') IS NOT NULL AS has_note_term_rel,
                to_regclass('public.xhs_author_metrics_30d') IS NOT NULL AS has_author_metrics,
                to_regclass('public.xhs_note_change_log') IS NOT NULL AS has_change_log,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'xhs_note_fact'
                      AND column_name = 'interaction_total'
                ) AS has_interaction_total,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'xhs_note_fact'
                      AND column_name = 'ext_payload'
                ) AS has_ext_payload
            """
        )
    ).mappings().first()
    if not row:
        return False
    return all(bool(row[key]) for key in row.keys())


def _seed_search_synonyms(db: Session) -> None:
    _safe_ddl(
        db,
        """
        INSERT INTO xhs_search_synonym_dim(term, synonym, lang, priority, status)
        VALUES
            ('防晒', 'sunscreen', 'mixed', 10, 'enabled'),
            ('sunscreen', '防晒', 'mixed', 10, 'enabled'),
            ('口红', 'lipstick', 'mixed', 10, 'enabled'),
            ('lipstick', '口红', 'mixed', 10, 'enabled'),
            ('粉底', 'foundation', 'mixed', 20, 'enabled'),
            ('foundation', '粉底', 'mixed', 20, 'enabled'),
            ('精华', 'serum', 'mixed', 20, 'enabled'),
            ('serum', '精华', 'mixed', 20, 'enabled'),
            ('面膜', 'mask', 'mixed', 20, 'enabled'),
            ('mask', '面膜', 'mixed', 20, 'enabled'),
            ('美妆', 'beauty', 'mixed', 30, 'enabled'),
            ('beauty', '美妆', 'mixed', 30, 'enabled')
        ON CONFLICT (term, synonym) DO UPDATE SET
            status = EXCLUDED.status,
            priority = LEAST(xhs_search_synonym_dim.priority, EXCLUDED.priority),
            updated_at = now()
        """,
    )


def _rebuild_interaction_total(db: Session) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_note_fact
            SET interaction_total =
                COALESCE(like_count, 0)
              + COALESCE(comment_count, 0)
              + COALESCE(collection_count, 0)
              + COALESCE(share_count, 0)
            WHERE COALESCE(interaction_total, 0) = 0
               OR interaction_total <> (
                    COALESCE(like_count, 0)
                  + COALESCE(comment_count, 0)
                  + COALESCE(collection_count, 0)
                  + COALESCE(share_count, 0)
               )
            """
        )
    )


def ensure_search_tables(db: Session) -> None:
    global _search_bootstrap_done
    if _search_bootstrap_done:
        return
    if _search_schema_ready(db):
        _search_bootstrap_done = True
        return

    lock_acquired = bool(
        db.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": _SEARCH_BOOTSTRAP_LOCK_KEY}).scalar()
    )
    if not lock_acquired:
        db.rollback()
        return
    try:
        if _search_bootstrap_done:
            return
        if _search_schema_ready(db):
            _search_bootstrap_done = True
            return
        db.execute(
            text("SET LOCAL lock_timeout = :timeout"),
            {"timeout": f"{_SEARCH_BOOTSTRAP_LOCK_TIMEOUT_MS}ms"},
        )
        ensure_industry_tables(db)
        _safe_ddl(
            db,
            """
                CREATE TABLE IF NOT EXISTS xhs_search_job (
                    job_id varchar(64) PRIMARY KEY,
                    search_type varchar(32) NOT NULL,
                    query varchar(255) NOT NULL,
                    mode varchar(32),
                    industry_key varchar(64),
                    status varchar(20) NOT NULL DEFAULT 'pending',
                    crawl_batch_id varchar(64),
                    task_id varchar(128),
                    request_payload jsonb,
                    response_payload jsonb,
                    error_msg text,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    completed_at timestamptz
                )
            """,
        )
        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_search_job_status ON xhs_search_job(status, created_at DESC)")
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_search_job_query ON xhs_search_job(search_type, query, created_at DESC)",
        )

        _safe_ddl(db, "CREATE EXTENSION IF NOT EXISTS pg_trgm", ignore_permission=True)
        _safe_ddl(db, "CREATE EXTENSION IF NOT EXISTS unaccent", ignore_permission=True)

        _safe_ddl(db, "ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS interaction_total bigint NOT NULL DEFAULT 0")
        _safe_ddl(db, "ALTER TABLE xhs_note_fact ADD COLUMN IF NOT EXISTS ext_payload jsonb")

        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_interaction_total ON xhs_note_fact(interaction_total DESC)")
        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_like_count ON xhs_note_fact(like_count DESC)")
        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_comment_count ON xhs_note_fact(comment_count DESC)")
        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_collection_count ON xhs_note_fact(collection_count DESC)")
        _safe_ddl(db, "CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_read_count ON xhs_note_fact(read_count DESC)")
        _safe_ddl(
            db,
            """
            CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_active_time
            ON xhs_note_fact((COALESCE(publish_time, updated_at, created_at)))
            """,
        )
        _safe_ddl(
            db,
            """
            CREATE INDEX IF NOT EXISTS idx_xhs_note_fact_search_blob_trgm
            ON xhs_note_fact
            USING gin (
                (
                    COALESCE(title, '')
                    || ' '
                    || COALESCE(content, '')
                    || ' '
                    || COALESCE(author_nickname, '')
                    || ' '
                    || COALESCE(search_keyword, '')
                ) gin_trgm_ops
            )
            """,
        )

        _safe_ddl(
            db,
            """
            CREATE TABLE IF NOT EXISTS xhs_search_synonym_dim (
                id bigserial PRIMARY KEY,
                term varchar(255) NOT NULL,
                synonym varchar(255) NOT NULL,
                lang varchar(8) NOT NULL DEFAULT 'mixed',
                priority integer NOT NULL DEFAULT 100,
                status varchar(20) NOT NULL DEFAULT 'enabled',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
        )
        _safe_ddl(
            db,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_search_synonym_dim_pair ON xhs_search_synonym_dim(term, synonym)",
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_search_synonym_dim_term ON xhs_search_synonym_dim(term, status)",
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_industry_rel_industry_note ON xhs_note_industry_rel(industry_key, note_id)",
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_crawl_log_status_created_task ON xhs_crawl_log(status, created_at DESC, task_type)",
        )
        _safe_ddl(
            db,
            """
            CREATE TABLE IF NOT EXISTS xhs_note_term_rel (
                id bigserial PRIMARY KEY,
                note_id varchar(64) NOT NULL,
                term varchar(255) NOT NULL,
                term_type varchar(32) NOT NULL DEFAULT 'text',
                weight integer NOT NULL DEFAULT 1,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
        )
        _safe_ddl(
            db,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_note_term_rel_note_term_type
            ON xhs_note_term_rel(note_id, term, term_type)
            """,
        )
        _safe_ddl(
            db,
            """
            CREATE INDEX IF NOT EXISTS idx_xhs_note_term_rel_term_weight_time
            ON xhs_note_term_rel(term, weight DESC, updated_at DESC)
            """,
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_term_rel_note_id ON xhs_note_term_rel(note_id)",
        )
        _safe_ddl(
            db,
            """
            CREATE TABLE IF NOT EXISTS xhs_author_metrics_30d (
                author_id varchar(128) PRIMARY KEY,
                author_nickname varchar(255),
                note_count bigint NOT NULL DEFAULT 0,
                interaction_total bigint NOT NULL DEFAULT 0,
                like_total bigint NOT NULL DEFAULT 0,
                comment_total bigint NOT NULL DEFAULT 0,
                collection_total bigint NOT NULL DEFAULT 0,
                share_total bigint NOT NULL DEFAULT 0,
                note_max_fans bigint NOT NULL DEFAULT 0,
                latest_data_at timestamptz,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_author_metrics_30d_interaction_total ON xhs_author_metrics_30d(interaction_total DESC)",
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_author_metrics_30d_latest_data_at ON xhs_author_metrics_30d(latest_data_at DESC)",
        )
        _safe_ddl(
            db,
            """
            CREATE TABLE IF NOT EXISTS xhs_note_change_log (
                id bigserial PRIMARY KEY,
                note_id varchar(64) NOT NULL,
                change_source varchar(64) NOT NULL DEFAULT 'unknown',
                changed_at timestamptz NOT NULL DEFAULT now(),
                processed_at timestamptz
            )
            """,
        )
        _safe_ddl(
            db,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_note_change_log_pending_note
            ON xhs_note_change_log(note_id)
            WHERE processed_at IS NULL
            """,
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_change_log_processed_changed ON xhs_note_change_log(processed_at, changed_at DESC)",
        )
        _safe_ddl(
            db,
            "CREATE INDEX IF NOT EXISTS idx_xhs_note_change_log_note_changed ON xhs_note_change_log(note_id, changed_at DESC)",
        )
        _seed_search_synonyms(db)
        db.commit()
        _search_bootstrap_done = True
    except Exception:
        db.rollback()
        if _search_schema_ready(db):
            _search_bootstrap_done = True
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": _SEARCH_BOOTSTRAP_LOCK_KEY})


def bootstrap_search_runtime() -> None:
    if _search_bootstrap_done:
        return

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        ensure_search_tables(db)
    finally:
        db.close()


def _normalize_query(value: str) -> str:
    return (value or "").strip()


def _split_query_tokens(value: str) -> list[str]:
    raw = _normalize_query(value)
    if not raw:
        return []
    parts = [item.strip() for item in re.split(r"[\s,，;；/|+]+", raw) if item.strip()]
    if raw not in parts:
        parts.insert(0, raw)
    return parts


def _domain_expand_terms(query: str) -> list[str]:
    return split_intent_terms(query, max_terms=20)


def _split_intent_terms(query: str, *, industry: str | None = None, max_terms: int = 20) -> IntentSplitResult:
    base = _normalize_query(query)
    intents = split_intent_terms(base, industry=industry, max_terms=max_terms)
    stopwords_removed = [token for token in _split_query_tokens(base) if token not in intents]
    return IntentSplitResult(original=base, intents=intents, stopwords_removed=stopwords_removed)


def _expand_query_terms(db: Session, query: str, *, industry: str | None = None) -> list[str]:
    base = _normalize_query(query)
    if not base:
        return split_intent_terms("", industry=industry, max_terms=24)

    split_result = _split_intent_terms(base, industry=industry, max_terms=24)
    terms = split_result.intents or [base]
    result = list(terms)
    seen = {item.casefold() for item in result}

    for seed in terms:
        rows = db.execute(
            text(
                """
                SELECT term AS item
                FROM xhs_search_synonym_dim
                WHERE status = 'enabled'
                  AND lower(synonym) = lower(:query)
                UNION
                SELECT synonym AS item
                FROM xhs_search_synonym_dim
                WHERE status = 'enabled'
                  AND lower(term) = lower(:query)
                """
            ),
            {"query": seed},
        ).scalars().all()

        for item in rows:
            token = str(item or "").strip()
            marker = token.casefold()
            if token and marker not in seen:
                seen.add(marker)
                result.append(token)

    return result[:24]


def _to_like_patterns(terms: list[str]) -> list[str]:
    return [f"%{term}%" for term in terms if term]


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


def _normalize_term_token(value: str | None, *, max_len: int = 255) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    token = re.sub(r"\s+", " ", token)
    if len(token) > max_len:
        token = token[:max_len]
    return token.casefold()


def _to_text_array(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items
    if isinstance(value, str):
        chunks = [item.strip() for item in re.split(r"[\s,，;；/|]+", value) if item.strip()]
        return chunks
    return []


def _build_note_terms(note: dict[str, Any], brand_aliases: list[str]) -> list[tuple[str, str, int]]:
    weighted: dict[tuple[str, str], int] = {}

    def put(term: str | None, term_type: str, weight: int) -> None:
        normalized = _normalize_term_token(term)
        if not normalized:
            return
        key = (normalized, term_type)
        current = weighted.get(key, 0)
        if weight > current:
            weighted[key] = weight

    keyword = str(note.get("search_keyword") or "").strip()
    if keyword:
        put(keyword, "keyword", 12)

    title = str(note.get("title") or "")
    content = str(note.get("content") or "")
    author = str(note.get("author_nickname") or "")
    tags = _to_text_array(note.get("tags"))

    if author:
        put(author, "author", 6)
    for tag in tags:
        put(tag, "tag", 8)
    for alias in brand_aliases:
        put(alias, "brand", 10)

    intents = split_intent_terms(" ".join([title, content]).strip(), max_terms=18)
    if keyword:
        intents.insert(0, keyword)
    for token in intents[:24]:
        put(token, "intent", 7)

    raw_parts = [title, content]
    for part in raw_parts:
        for token in _to_text_array(part):
            put(token, "text", 4)

    return [(term, term_type, weight) for (term, term_type), weight in weighted.items()]


def enqueue_note_change_events(db: Session, *, note_ids: list[str], source: str) -> int:
    ensure_search_tables(db)
    normalized = [str(item).strip() for item in note_ids if str(item).strip()]
    if not normalized:
        return 0
    deduped = list(dict.fromkeys(normalized))
    db.execute(
        text(
            """
            INSERT INTO xhs_note_change_log(note_id, change_source, changed_at)
            SELECT note_id, :source, now()
            FROM unnest(CAST(:note_ids AS text[])) AS t(note_id)
            ON CONFLICT (note_id) WHERE processed_at IS NULL
            DO UPDATE SET
                change_source = EXCLUDED.change_source,
                changed_at = EXCLUDED.changed_at
            """
        ),
        {"source": source[:64], "note_ids": deduped},
    )
    return len(deduped)


def _refresh_note_terms_for_notes(db: Session, *, note_ids: list[str]) -> int:
    if not note_ids:
        return 0
    rows = db.execute(
        text(
            """
            SELECT note_id, title, content, author_nickname, search_keyword, tags
            FROM xhs_note_fact
            WHERE note_id = ANY(CAST(:note_ids AS text[]))
            """
        ),
        {"note_ids": note_ids},
    ).mappings().all()
    brand_rows = db.execute(
        text(
            """
            SELECT note_id, brand_name
            FROM xhs_note_brand_rel
            WHERE note_id = ANY(CAST(:note_ids AS text[]))
            """
        ),
        {"note_ids": note_ids},
    ).mappings().all()
    brand_map: dict[str, list[str]] = {}
    for item in brand_rows:
        note_id = str(item.get("note_id") or "")
        brand = str(item.get("brand_name") or "").strip()
        if not note_id or not brand:
            continue
        brand_map.setdefault(note_id, []).append(brand)

    db.execute(
        text("DELETE FROM xhs_note_term_rel WHERE note_id = ANY(CAST(:note_ids AS text[]))"),
        {"note_ids": note_ids},
    )

    inserted = 0
    for row in rows:
        note_id = str(row.get("note_id") or "").strip()
        if not note_id:
            continue
        terms = _build_note_terms(dict(row), brand_map.get(note_id, []))
        if not terms:
            continue
        db.execute(
            text(
                """
                INSERT INTO xhs_note_term_rel(note_id, term, term_type, weight, updated_at)
                SELECT
                    :note_id,
                    LEFT(COALESCE(t.term, ''), 255),
                    LEFT(COALESCE(t.term_type, 'text'), 32),
                    GREATEST(COALESCE(t.weight, 1), 1),
                    now()
                FROM jsonb_to_recordset(CAST(:items AS jsonb)) AS t(term text, term_type text, weight integer)
                WHERE COALESCE(t.term, '') <> ''
                ON CONFLICT (note_id, term, term_type)
                DO UPDATE SET
                    weight = EXCLUDED.weight,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "note_id": note_id,
                "items": json.dumps(
                    [{"term": term, "term_type": term_type, "weight": weight} for term, term_type, weight in terms],
                    ensure_ascii=False,
                ),
            },
        )
        inserted += len(terms)
    return inserted


def _refresh_author_metrics_for_authors(db: Session, *, author_ids: list[str]) -> int:
    if not author_ids:
        return 0
    db.execute(
        text("DELETE FROM xhs_author_metrics_30d WHERE author_id = ANY(CAST(:author_ids AS text[]))"),
        {"author_ids": author_ids},
    )
    window_days = max(1, int(settings.search_incremental_author_window_days))
    db.execute(
        text(
            """
            INSERT INTO xhs_author_metrics_30d(
                author_id, author_nickname, note_count, interaction_total, like_total, comment_total,
                collection_total, share_total, note_max_fans, latest_data_at, updated_at
            )
            SELECT
                f.author_id,
                MAX(COALESCE(f.author_nickname, '')) AS author_nickname,
                COUNT(*)::bigint AS note_count,
                SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0)))::bigint AS interaction_total,
                SUM(COALESCE(f.like_count, 0))::bigint AS like_total,
                SUM(COALESCE(f.comment_count, 0))::bigint AS comment_total,
                SUM(COALESCE(f.collection_count, 0))::bigint AS collection_total,
                SUM(COALESCE(f.share_count, 0))::bigint AS share_total,
                MAX(COALESCE(f.author_fans_count, 0))::bigint AS note_max_fans,
                MAX(COALESCE(f.updated_at, f.created_at, f.publish_time)) AS latest_data_at,
                now()
            FROM xhs_note_fact f
            WHERE f.author_id = ANY(CAST(:author_ids AS text[]))
              AND f.author_id IS NOT NULL
              AND f.author_id <> ''
              AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:window_days)::text || ' day')::interval
            GROUP BY f.author_id
            """
        ),
        {"author_ids": author_ids, "window_days": window_days},
    )
    return len(author_ids)


def process_note_change_log(db: Session, *, batch_size: int | None = None) -> dict[str, int]:
    ensure_search_tables(db)
    size = max(1, int(batch_size or settings.search_incremental_batch_size))
    change_rows = db.execute(
        text(
            """
            SELECT id, note_id
            FROM xhs_note_change_log
            WHERE processed_at IS NULL
            ORDER BY changed_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
            """
        ),
        {"limit": size},
    ).mappings().all()
    if not change_rows:
        return {"changes": 0, "notes": 0, "authors": 0, "terms": 0}

    change_ids = [int(row["id"]) for row in change_rows]
    note_ids = list(dict.fromkeys(str(row["note_id"]).strip() for row in change_rows if str(row["note_id"]).strip()))
    if not note_ids:
        db.execute(
            text("UPDATE xhs_note_change_log SET processed_at = now() WHERE id = ANY(CAST(:ids AS bigint[]))"),
            {"ids": change_ids},
        )
        return {"changes": len(change_ids), "notes": 0, "authors": 0, "terms": 0}

    term_rows = _refresh_note_terms_for_notes(db, note_ids=note_ids)
    author_ids = db.execute(
        text(
            """
            SELECT DISTINCT author_id
            FROM xhs_note_fact
            WHERE note_id = ANY(CAST(:note_ids AS text[]))
              AND author_id IS NOT NULL
              AND author_id <> ''
            """
        ),
        {"note_ids": note_ids},
    ).scalars().all()
    normalized_authors = [str(item).strip() for item in author_ids if str(item).strip()]
    refreshed_authors = _refresh_author_metrics_for_authors(db, author_ids=normalized_authors)

    db.execute(
        text(
            """
            UPDATE xhs_note_change_log
            SET processed_at = now()
            WHERE id = ANY(CAST(:ids AS bigint[]))
            """
        ),
        {"ids": change_ids},
    )
    return {
        "changes": len(change_ids),
        "notes": len(note_ids),
        "authors": refreshed_authors,
        "terms": term_rows,
    }


def maybe_refresh_incremental_search_artifacts(db: Session) -> dict[str, int]:
    global _incremental_refresh_last_at
    ensure_search_tables(db)
    now_ts = time.monotonic()
    min_interval = max(5, int(settings.search_incremental_refresh_interval_seconds))
    if now_ts - _incremental_refresh_last_at < min_interval:
        return {"changes": 0, "notes": 0, "authors": 0, "terms": 0}
    _incremental_refresh_last_at = now_ts
    try:
        result = process_note_change_log(db, batch_size=settings.search_incremental_batch_size)
        db.commit()
        return result
    except Exception:
        db.rollback()
        return {"changes": 0, "notes": 0, "authors": 0, "terms": 0}


def get_term_rel_coverage_stats(db: Session) -> dict[str, Any]:
    ensure_search_tables(db)
    row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM xhs_note_fact) AS note_total,
                (SELECT COUNT(DISTINCT note_id) FROM xhs_note_term_rel) AS term_note_total,
                (SELECT COUNT(*) FROM xhs_note_change_log WHERE processed_at IS NULL) AS change_log_pending
            """
        )
    ).mappings().first()
    note_total = int((row or {}).get("note_total") or 0)
    term_note_total = int((row or {}).get("term_note_total") or 0)
    change_log_pending = int((row or {}).get("change_log_pending") or 0)
    coverage_ratio = float(term_note_total / note_total) if note_total > 0 else 0.0
    return {
        "note_total": note_total,
        "term_note_total": term_note_total,
        "change_log_pending": change_log_pending,
        "coverage_ratio": coverage_ratio,
    }


def evaluate_result_health(
    result: dict[str, Any],
    *,
    min_results: int,
    stale_hours: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    pagination = result.get("pagination") if isinstance(result.get("pagination"), dict) else {}
    total = int((pagination or {}).get("total") or 0)
    freshness_raw = str(result.get("freshness") or "")
    freshness_dt = _parse_iso_datetime(freshness_raw)
    baseline = now or datetime.now(timezone.utc)
    reasons: list[str] = []

    if total < max(0, min_results):
        reasons.append("low_results")
    if freshness_dt is None:
        reasons.append("missing_freshness")
    else:
        age_hours = (baseline - freshness_dt).total_seconds() / 3600
        if age_hours > max(1 / 60, float(stale_hours)):
            reasons.append("stale_data")

    return {
        "healthy": len(reasons) == 0,
        "total": total,
        "freshness": freshness_raw or None,
        "reasons": reasons,
    }


def build_fetch_decision(
    result: dict[str, Any],
    *,
    force_refresh: bool,
    min_results: int,
    stale_hours: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    health = evaluate_result_health(
        result,
        min_results=min_results,
        stale_hours=stale_hours,
        now=now,
    )
    reasons = list(health["reasons"])
    if force_refresh:
        reasons.insert(0, "force_refresh")
    need_fetch = bool(force_refresh) or (not bool(health["healthy"]))
    decision = FetchDecision(
        need_fetch=need_fetch,
        reasons=reasons,
        health=health,
    )
    return {
        "need_fetch": decision.need_fetch,
        "reasons": decision.reasons,
        "health": decision.health,
    }


def _is_fresh(latest_at: datetime | None, freshness_hours: int) -> bool:
    if not latest_at:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(freshness_hours, 1))
    if latest_at.tzinfo is None:
        latest_at = latest_at.replace(tzinfo=timezone.utc)
    return latest_at >= cutoff


def _parse_follower_range(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        return None, None
    low = int(parts[0]) if parts[0].isdigit() else None
    high = int(parts[1]) if parts[1].isdigit() else None
    return low, high


def _parse_interaction_range(raw: str | None) -> tuple[int | None, int | None]:
    return _parse_follower_range(raw)


def _creator_order_clause(sort: CreatorSortKey, order: SortOrder) -> str:
    direction = "ASC" if order == "asc" else "DESC"
    effective_anchor_fans = "COALESCE(a.fans_count, an.fans_count)"
    mapping = {
        "relevance": (
            "("
            "LEAST(COALESCE(s.matched_note_count, 0), 120) * 8"
            " + LEAST(COALESCE(s.interaction_total, 0) / 400, 600)"
            " + CASE"
            "     WHEN s.latest_data_at >= now() - interval '3 day' THEN 30"
            "     WHEN s.latest_data_at >= now() - interval '7 day' THEN 18"
            "     WHEN s.latest_data_at >= now() - interval '30 day' THEN 6"
            "     ELSE 0"
            "   END"
            ")"
        ),
        "followers": f"COALESCE(NULLIF({effective_anchor_fans}, 0), NULLIF(s.note_max_fans, 0), 0)",
        "notes": "s.matched_note_count",
        "sumStat": "s.interaction_total",
    }
    expr = mapping.get(sort, mapping["relevance"])
    return f"{expr} {direction}, s.matched_note_count DESC, s.author_id ASC"


def _category_order_clause(sort: CategorySortKey, order: SortOrder) -> str:
    direction = "ASC" if order == "asc" else "DESC"
    mapping = {
        "stat": "COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))",
        "like": "COALESCE(f.like_count, 0)",
        "read": "COALESCE(f.read_count, 0)",
        "comments": "COALESCE(f.comment_count, 0)",
    }
    expr = mapping.get(sort, mapping["stat"])
    return f"{expr} {direction}, COALESCE(f.publish_time, f.updated_at, f.created_at) DESC"


def _bounded_page_size(size: int) -> int:
    # 后端硬阈值，防止误传导致全表重压。
    return max(1, min(int(size or 1), 100))


def _search_blob_expr(alias: str) -> str:
    # Keep the exact expression in sync with idx_xhs_note_fact_search_blob_trgm.
    return (
        f"COALESCE({alias}.title, '')"
        " || ' ' || "
        f"COALESCE({alias}.content, '')"
        " || ' ' || "
        f"COALESCE({alias}.author_nickname, '')"
        " || ' ' || "
        f"COALESCE({alias}.search_keyword, '')"
    )


def _build_text_match_exists_clause(*, alias: str, pattern_param: str = "query_patterns") -> str:
    blob_expr = _search_blob_expr(alias)
    return (
        "EXISTS ("
        f"SELECT 1 FROM unnest(CAST(:{pattern_param} AS text[])) AS qp(pattern) "
        f"WHERE ({blob_expr}) ILIKE qp.pattern"
        ")"
    )


def create_search_job(
    db: Session,
    *,
    search_type: SearchType,
    query: str,
    mode: str | None,
    industry: str | None,
    request_payload: dict[str, Any],
) -> str:
    job_id = uuid.uuid4().hex[:20]
    industry_key = resolve_industry_key(industry) or resolve_industry_key(query)
    db.execute(
        text(
            """
            INSERT INTO xhs_search_job(
                job_id, search_type, query, mode, industry_key, status, request_payload
            ) VALUES (
                :job_id, :search_type, :query, :mode, :industry_key, 'pending', CAST(:request_payload AS jsonb)
            )
            """
        ),
        {
            "job_id": job_id,
            "search_type": search_type,
            "query": query,
            "mode": mode,
            "industry_key": industry_key,
            "request_payload": json.dumps(request_payload, ensure_ascii=False),
        },
    )
    db.commit()
    return job_id


def mark_search_job_running(
    db: Session,
    *,
    job_id: str,
    crawl_batch_id: str | None = None,
    task_id: str | None = None,
) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_search_job
            SET status = 'running',
                crawl_batch_id = COALESCE(:crawl_batch_id, crawl_batch_id),
                task_id = COALESCE(:task_id, task_id),
                updated_at = now()
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id, "crawl_batch_id": crawl_batch_id, "task_id": task_id},
    )
    db.commit()


def mark_search_job_ready(db: Session, *, job_id: str, response_payload: dict[str, Any] | None = None) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_search_job
            SET status = 'ready',
                response_payload = CAST(:response_payload AS jsonb),
                completed_at = now(),
                updated_at = now()
            WHERE job_id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "response_payload": json.dumps(response_payload or {}, ensure_ascii=False),
        },
    )
    db.commit()


def mark_search_job_failed(db: Session, *, job_id: str, error_msg: str) -> None:
    db.execute(
        text(
            """
            UPDATE xhs_search_job
            SET status = 'failed',
                error_msg = :error_msg,
                completed_at = now(),
                updated_at = now()
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id, "error_msg": error_msg[:1000]},
    )
    db.commit()


def get_search_job(db: Session, job_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT job_id, search_type, query, mode, industry_key, status, crawl_batch_id,
                   task_id, request_payload, response_payload, error_msg,
                   created_at, updated_at, completed_at
            FROM xhs_search_job
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().first()
    if not row:
        return None
    data = dict(row)
    for key in ("created_at", "updated_at", "completed_at"):
        if data.get(key):
            data[key] = data[key].isoformat()
    return data


def try_sync_job_status_with_crawl(db: Session, *, job_id: str) -> dict[str, Any] | None:
    job = get_search_job(db, job_id)
    if not job:
        return None
    if job["status"] in {"ready", "failed"}:
        return job
    crawl_batch_id = job.get("crawl_batch_id")
    if not crawl_batch_id:
        return job

    crawl = db.execute(
        text(
            """
            SELECT status, row_count, error_msg
            FROM xhs_crawl_log
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": crawl_batch_id},
    ).mappings().first()
    if not crawl:
        return job

    crawl_status = str(crawl.get("status") or "").strip()
    if crawl_status == "success":
        row_count = int(crawl.get("row_count") or 0)
        if row_count > 0:
            mark_search_job_ready(
                db,
                job_id=job_id,
                response_payload={"crawl_batch_id": crawl_batch_id, "row_count": row_count},
            )
        else:
            mark_search_job_failed(
                db,
                job_id=job_id,
                error_msg="no_results_after_fetch",
            )
    elif crawl_status in {"failed", "failed_timeout", "timeout"}:
        mark_search_job_failed(db, job_id=job_id, error_msg=str(crawl.get("error_msg") or "crawl failed"))
    return get_search_job(db, job_id)


def _category_order_expr_v2(sort: CategorySortKey) -> str:
    mapping = {
        "stat": "COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))",
        "like": "COALESCE(f.like_count, 0)",
        "read": "COALESCE(f.read_count, 0)",
        "comments": "COALESCE(f.comment_count, 0)",
    }
    return mapping.get(sort, mapping["stat"])


def _creator_order_expr_v2(sort: CreatorSortKey) -> str:
    mapping = {
        "relevance": (
            "("
            "LEAST(COALESCE(s.matched_note_count, 0), 120) * 8"
            " + LEAST(COALESCE(GREATEST(COALESCE(s.interaction_total, 0), COALESCE(m.interaction_total, 0)), 0) / 400, 600)"
            " + CASE"
            "     WHEN COALESCE(s.latest_data_at, m.latest_data_at) >= now() - interval '3 day' THEN 30"
            "     WHEN COALESCE(s.latest_data_at, m.latest_data_at) >= now() - interval '7 day' THEN 18"
            "     WHEN COALESCE(s.latest_data_at, m.latest_data_at) >= now() - interval '30 day' THEN 6"
            "     ELSE 0"
            "   END"
            ")"
        ),
        "followers": "COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), 0)",
        "notes": "GREATEST(COALESCE(m.note_count, 0), COALESCE(s.matched_note_count, 0))",
        "sumStat": "GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0))",
    }
    return mapping.get(sort, mapping["relevance"])


def query_brand_category_db_first_v2(
    db: Session,
    *,
    query: str,
    mode: Literal["brand", "category"],
    industry: str | None,
    min_like: int,
    date_range: int,
    page: int,
    size: int,
    freshness_hours: int,
    sort: CategorySortKey = "stat",
    order: SortOrder = "desc",
) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        return query_brand_category_db_first(
            db,
            query=query,
            mode=mode,
            industry=industry,
            min_like=min_like,
            date_range=date_range,
            page=page,
            size=size,
            freshness_hours=freshness_hours,
            sort=sort,
            order=order,
        )

    industry_key = resolve_industry_key(industry)
    query_terms = _expand_query_terms(db, query, industry=industry)
    if not query_terms:
        query_terms = [normalized_query]
    size = _bounded_page_size(size)
    offset = max(page - 1, 0) * size
    candidate_limit = max(size * 20, int(settings.search_v2_candidate_limit))
    direction = "ASC" if order == "asc" else "DESC"
    order_expr = _category_order_expr_v2(sort)
    order_clause = f"{order_expr} {direction}, COALESCE(f.publish_time, f.updated_at, f.created_at) DESC"
    if mode == "category":
        order_clause = f"c.term_score DESC, {order_clause}"

    params = {
        "query_terms": query_terms,
        "candidate_limit": candidate_limit,
        "min_like": min_like,
        "date_range": date_range,
        "industry_key": industry_key,
        "mode": mode,
        "query_limit": size + 1,
        "offset": offset,
    }

    rows = db.execute(
        text(
            f"""
            WITH candidate_notes AS (
                SELECT
                    r.note_id,
                    MAX(r.weight)::int AS term_score,
                    MAX(r.updated_at) AS term_updated_at
                FROM xhs_note_term_rel r
                WHERE r.term = ANY(CAST(:query_terms AS text[]))
                GROUP BY r.note_id
                ORDER BY term_score DESC, term_updated_at DESC
                LIMIT :candidate_limit
            )
            SELECT
                f.note_id,
                f.title,
                f.author_id,
                f.author_nickname,
                f.search_keyword,
                COALESCE(f.like_count, 0) AS like_count,
                COALESCE(f.comment_count, 0) AS comment_count,
                COALESCE(f.collection_count, 0) AS collection_count,
                COALESCE(f.share_count, 0) AS share_count,
                COALESCE(f.read_count, 0) AS read_count,
                COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0)) AS interaction_total,
                c.term_score,
                COALESCE(f.publish_time, f.updated_at, f.created_at) AS publish_time,
                COALESCE(f.updated_at, f.created_at) AS latest_data_at
            FROM candidate_notes c
            JOIN xhs_note_fact f ON f.note_id = c.note_id
            WHERE COALESCE(f.like_count, 0) >= :min_like
              AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
              AND (
                    (:industry_key)::text IS NULL
                 OR EXISTS (
                        SELECT 1
                        FROM xhs_note_industry_rel nir
                        WHERE nir.note_id = f.note_id
                          AND nir.industry_key = (:industry_key)::text
                    )
              )
              AND (
                    (:mode)::text = 'category'
                    OR EXISTS (
                        SELECT 1
                        FROM xhs_note_brand_rel rel
                        WHERE rel.note_id = f.note_id
                          AND rel.brand_name = ANY(CAST(:query_terms AS text[]))
                    )
              )
            ORDER BY {order_clause}
            LIMIT :query_limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    total = int(
        db.execute(
            text(
                """
                WITH candidate_notes AS (
                    SELECT
                        r.note_id,
                        MAX(r.weight)::int AS term_score,
                        MAX(r.updated_at) AS term_updated_at
                    FROM xhs_note_term_rel r
                    WHERE r.term = ANY(CAST(:query_terms AS text[]))
                    GROUP BY r.note_id
                    ORDER BY term_score DESC, term_updated_at DESC
                    LIMIT :candidate_limit
                )
                SELECT COUNT(*)::bigint
                FROM candidate_notes c
                JOIN xhs_note_fact f ON f.note_id = c.note_id
                WHERE COALESCE(f.like_count, 0) >= :min_like
                  AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                  AND (
                        (:industry_key)::text IS NULL
                     OR EXISTS (
                            SELECT 1
                            FROM xhs_note_industry_rel nir
                            WHERE nir.note_id = f.note_id
                              AND nir.industry_key = (:industry_key)::text
                        )
                  )
                  AND (
                        (:mode)::text = 'category'
                        OR EXISTS (
                            SELECT 1
                            FROM xhs_note_brand_rel rel
                            WHERE rel.note_id = f.note_id
                              AND rel.brand_name = ANY(CAST(:query_terms AS text[]))
                        )
                  )
                """
            ),
            params,
        ).scalar()
        or 0
    )
    has_more = len(rows) > size
    page_rows = rows[:size]
    has_more = has_more or (offset + len(page_rows) < total)
    latest_dt = max((row.get("latest_data_at") for row in page_rows if row.get("latest_data_at")), default=None)
    items: list[dict[str, Any]] = []
    creators: set[str] = set()
    for row in page_rows:
        item = dict(row)
        creators.add(str(item.get("author_id") or "").strip())
        if item.get("publish_time"):
            item["publish_time"] = item["publish_time"].isoformat()
        if item.get("latest_data_at"):
            item["latest_data_at"] = item["latest_data_at"].isoformat()
        item["post_url"] = f"https://www.xiaohongshu.com/explore/{item['note_id']}"
        items.append(item)

    summary = {
        "note_count": total,
        "creator_count": len([c for c in creators if c]),
        "like_total": sum(int(item.get("like_count") or 0) for item in items),
        "comment_total": sum(int(item.get("comment_count") or 0) for item in items),
        "collection_total": sum(int(item.get("collection_count") or 0) for item in items),
    }
    freshness = latest_dt.isoformat() if latest_dt else None
    return {
        "hit": total > 0,
        "summary": summary,
        "items": items,
        "pagination": {
            "total": total,
            "page": page,
            "size": size,
            "has_more": has_more,
            "total_is_estimate": True,
        },
        "freshness": freshness,
    }


def query_influencers_db_first_v2(
    db: Session,
    *,
    query: str,
    industry: str | None,
    follower_range: str | None,
    interaction_range: str | None,
    date_range: int,
    page: int,
    size: int,
    freshness_hours: int,
    sort: CreatorSortKey = "relevance",
    order: SortOrder = "desc",
    include_notes: bool = False,
) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        return query_influencers_db_first(
            db,
            query=query,
            industry=industry,
            follower_range=follower_range,
            interaction_range=interaction_range,
            date_range=date_range,
            page=page,
            size=size,
            freshness_hours=freshness_hours,
            sort=sort,
            order=order,
            include_notes=include_notes,
        )

    industry_key = resolve_industry_key(industry) or resolve_industry_key(query)
    follower_min, follower_max = _parse_follower_range(follower_range)
    interaction_min, interaction_max = _parse_interaction_range(interaction_range)
    query_terms = _expand_query_terms(db, query, industry=industry)
    if not query_terms:
        query_terms = [normalized_query]
    size = _bounded_page_size(size)
    offset = max(page - 1, 0) * size
    candidate_limit = max(size * 30, int(settings.search_v2_note_candidate_limit))
    direction = "ASC" if order == "asc" else "DESC"
    order_clause = f"{_creator_order_expr_v2(sort)} {direction}, s.matched_note_count DESC, s.author_id ASC"

    params = {
        "query_terms": query_terms,
        "candidate_limit": candidate_limit,
        "industry_key": industry_key,
        "date_range": date_range,
        "follower_min": follower_min,
        "follower_max": follower_max,
        "interaction_min": interaction_min,
        "interaction_max": interaction_max,
        "query_limit": size + 1,
        "offset": offset,
    }

    rows = db.execute(
        text(
            f"""
            WITH candidate_notes AS (
                SELECT
                    r.note_id,
                    MAX(r.weight)::int AS term_score,
                    MAX(r.updated_at) AS term_updated_at
                FROM xhs_note_term_rel r
                WHERE r.term = ANY(CAST(:query_terms AS text[]))
                GROUP BY r.note_id
                ORDER BY term_score DESC, term_updated_at DESC
                LIMIT :candidate_limit
            ),
            scoped_notes AS (
                SELECT f.*
                FROM candidate_notes c
                JOIN xhs_note_fact f ON f.note_id = c.note_id
                LEFT JOIN xhs_note_industry_rel rel
                  ON rel.note_id = f.note_id
                 AND rel.industry_key = (:industry_key)::text
                WHERE f.author_id IS NOT NULL
                  AND f.author_id <> ''
                  AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                  AND ((:industry_key)::text IS NULL OR rel.note_id IS NOT NULL)
            ),
            author_stats AS (
                SELECT
                    n.author_id,
                    MAX(COALESCE(n.author_nickname, '')) AS author_nickname,
                    COUNT(*)::bigint AS matched_note_count,
                    MAX(COALESCE(n.author_fans_count, 0))::bigint AS note_max_fans,
                    SUM(COALESCE(n.like_count, 0))::bigint AS like_total,
                    SUM(COALESCE(n.comment_count, 0))::bigint AS comment_total,
                    SUM(COALESCE(n.collection_count, 0))::bigint AS collection_total,
                    SUM(COALESCE(n.share_count, 0))::bigint AS share_total,
                    SUM(COALESCE(n.interaction_total, COALESCE(n.like_count,0)+COALESCE(n.comment_count,0)+COALESCE(n.collection_count,0)+COALESCE(n.share_count,0)))::bigint AS interaction_total,
                    MAX(COALESCE(n.updated_at, n.created_at)) AS latest_data_at
                FROM scoped_notes n
                GROUP BY n.author_id
            )
            SELECT
                s.author_id,
                s.author_nickname,
                COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), NULLIF(s.note_max_fans, 0), 0) AS followers,
                COALESCE(a.tag_list, ARRAY[]::text[]) AS tag_list,
                COALESCE(NULLIF(a.anchor_link, ''), 'https://www.xiaohongshu.com/user/profile/' || s.author_id) AS creator_home_url,
                GREATEST(COALESCE(m.note_count, 0), COALESCE(s.matched_note_count, 0))::bigint AS note_count,
                s.matched_note_count,
                ({_creator_order_expr_v2('relevance')})::bigint AS relevance_score,
                s.like_total,
                s.comment_total,
                s.collection_total,
                s.share_total,
                GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0))::bigint AS interaction_total,
                COALESCE(s.latest_data_at, m.latest_data_at) AS latest_data_at
            FROM author_stats s
            LEFT JOIN xhs_author_metrics_30d m ON m.author_id = s.author_id
            LEFT JOIN xhs_anchor_dim a ON a.author_id = s.author_id
            WHERE ((:follower_min)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), NULLIF(s.note_max_fans, 0), 0) >= (:follower_min)::bigint)
              AND ((:follower_max)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), NULLIF(s.note_max_fans, 0), 0) <= (:follower_max)::bigint)
              AND ((:interaction_min)::bigint IS NULL OR GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0)) >= (:interaction_min)::bigint)
              AND ((:interaction_max)::bigint IS NULL OR GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0)) <= (:interaction_max)::bigint)
            ORDER BY {order_clause}
            LIMIT :query_limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    total = int(
        db.execute(
            text(
                f"""
                WITH candidate_notes AS (
                    SELECT
                        r.note_id,
                        MAX(r.weight)::int AS term_score,
                        MAX(r.updated_at) AS term_updated_at
                    FROM xhs_note_term_rel r
                    WHERE r.term = ANY(CAST(:query_terms AS text[]))
                    GROUP BY r.note_id
                    ORDER BY term_score DESC, term_updated_at DESC
                    LIMIT :candidate_limit
                ),
                scoped_notes AS (
                    SELECT f.*
                    FROM candidate_notes c
                    JOIN xhs_note_fact f ON f.note_id = c.note_id
                    LEFT JOIN xhs_note_industry_rel rel
                      ON rel.note_id = f.note_id
                     AND rel.industry_key = (:industry_key)::text
                    WHERE f.author_id IS NOT NULL
                      AND f.author_id <> ''
                      AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                      AND ((:industry_key)::text IS NULL OR rel.note_id IS NOT NULL)
                ),
                author_stats AS (
                    SELECT
                        n.author_id,
                        MAX(COALESCE(n.author_nickname, '')) AS author_nickname,
                        COUNT(*)::bigint AS matched_note_count,
                        MAX(COALESCE(n.author_fans_count, 0))::bigint AS note_max_fans,
                        SUM(COALESCE(n.like_count, 0))::bigint AS like_total,
                        SUM(COALESCE(n.comment_count, 0))::bigint AS comment_total,
                        SUM(COALESCE(n.collection_count, 0))::bigint AS collection_total,
                        SUM(COALESCE(n.share_count, 0))::bigint AS share_total,
                        SUM(COALESCE(n.interaction_total, COALESCE(n.like_count,0)+COALESCE(n.comment_count,0)+COALESCE(n.collection_count,0)+COALESCE(n.share_count,0)))::bigint AS interaction_total
                    FROM scoped_notes n
                    GROUP BY n.author_id
                )
                SELECT COUNT(*)::bigint
                FROM author_stats s
                LEFT JOIN xhs_author_metrics_30d m ON m.author_id = s.author_id
                LEFT JOIN xhs_anchor_dim a ON a.author_id = s.author_id
                WHERE ((:follower_min)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), NULLIF(s.note_max_fans, 0), 0) >= (:follower_min)::bigint)
                  AND ((:follower_max)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, m.note_max_fans), 0), NULLIF(s.note_max_fans, 0), 0) <= (:follower_max)::bigint)
                  AND ((:interaction_min)::bigint IS NULL OR GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0)) >= (:interaction_min)::bigint)
                  AND ((:interaction_max)::bigint IS NULL OR GREATEST(COALESCE(m.interaction_total, 0), COALESCE(s.interaction_total, 0)) <= (:interaction_max)::bigint)
                """
            ),
            params,
        ).scalar()
        or 0
    )
    has_more = len(rows) > size
    page_rows = rows[:size]
    has_more = has_more or (offset + len(page_rows) < total)
    latest_dt = max((row.get("latest_data_at") for row in page_rows if row.get("latest_data_at")), default=None)
    items: list[dict[str, Any]] = []
    author_ids = [
        str(row.get("author_id") or "").strip() for row in page_rows if str(row.get("author_id") or "").strip()
    ]
    for row in page_rows:
        item = dict(row)
        if item.get("latest_data_at"):
            item["latest_data_at"] = item["latest_data_at"].isoformat()
        item["tags"] = item.pop("tag_list", []) or []
        items.append(item)

    notes: list[dict[str, Any]] = []
    if include_notes and author_ids:
        note_rows = db.execute(
            text(
                """
                SELECT
                    note_id, author_id, author_nickname, title, publish_time,
                    like_count, comment_count, collection_count, share_count
                FROM xhs_note_fact
                WHERE author_id = ANY(CAST(:author_ids AS text[]))
                ORDER BY COALESCE(interaction_total, COALESCE(like_count,0)+COALESCE(comment_count,0)+COALESCE(collection_count,0)+COALESCE(share_count,0)) DESC,
                         publish_time DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"author_ids": author_ids, "limit": min(300, size * 10)},
        ).mappings().all()
        for row in note_rows:
            note = dict(row)
            if note.get("publish_time"):
                note["publish_time"] = note["publish_time"].isoformat()
            note["post_url"] = f"https://www.xiaohongshu.com/explore/{note['note_id']}"
            notes.append(note)

    summary = {
        "creator_count": total,
        "note_count": sum(int(item.get("note_count") or 0) for item in items),
        "like_total": sum(int(item.get("like_total") or 0) for item in items),
        "comment_total": sum(int(item.get("comment_total") or 0) for item in items),
        "collection_total": sum(int(item.get("collection_total") or 0) for item in items),
    }
    freshness = latest_dt.isoformat() if latest_dt else None
    return {
        "hit": total > 0,
        "summary": summary,
        "items": items,
        "notes": notes,
        "pagination": {
            "total": total,
            "page": page,
            "size": size,
            "has_more": has_more,
            "total_is_estimate": True,
        },
        "freshness": freshness,
    }


def query_influencers_db_first(
    db: Session,
    *,
    query: str,
    industry: str | None,
    follower_range: str | None,
    interaction_range: str | None,
    date_range: int,
    page: int,
    size: int,
    freshness_hours: int,
    sort: CreatorSortKey = "relevance",
    order: SortOrder = "desc",
    include_notes: bool = False,
) -> dict[str, Any]:
    size = _bounded_page_size(size)
    industry_key = resolve_industry_key(industry) or resolve_industry_key(query)
    follower_min, follower_max = _parse_follower_range(follower_range)
    interaction_min, interaction_max = _parse_interaction_range(interaction_range)
    query_terms = _expand_query_terms(db, query, industry=industry)
    query_patterns = _to_like_patterns(query_terms)
    normalized_query = _normalize_query(query)
    offset = max(page - 1, 0) * size
    direction = "ASC" if order == "asc" else "DESC"
    sort_by_total_notes = sort == "notes"
    order_clause = (
        "GREATEST(COALESCE(at.total_note_count, 0), COALESCE(a.total_note_count, 0), COALESCE(an.total_note_count, 0), COALESCE(s.matched_note_count, 0)) "
        f"{direction}, s.matched_note_count DESC, s.author_id ASC"
        if sort_by_total_notes
        else _creator_order_clause(sort, order)
    )
    text_match_clause = _build_text_match_exists_clause(alias="n")
    cte_author_totals = (
        """
            ,
            author_totals AS (
                SELECT
                    f.author_id,
                    COUNT(*)::bigint AS total_note_count
                FROM xhs_note_fact f
                JOIN author_stats s ON s.author_id = f.author_id
                GROUP BY f.author_id
            )
        """
        if sort_by_total_notes
        else ""
    )
    join_author_totals = "LEFT JOIN author_totals at ON at.author_id = s.author_id" if sort_by_total_notes else ""

    exact_where_query = """
        (
                :query = ''
             OR n.author_id = ANY(CAST(:query_terms AS text[]))
             OR COALESCE(n.search_keyword, '') = ANY(CAST(:query_terms AS text[]))
        )
    """
    fuzzy_where_query = """
        (
                :query = ''
             OR n.author_id = ANY(CAST(:query_terms AS text[]))
             OR COALESCE(n.search_keyword, '') = ANY(CAST(:query_terms AS text[]))
             OR {text_match_clause}
        )
    """.format(text_match_clause=text_match_clause)

    params = {
        "query": normalized_query,
        "query_terms": query_terms or [normalized_query],
        "query_patterns": query_patterns or ([f"%{normalized_query}%"] if normalized_query else ["%%"]),
        "industry_key": industry_key,
        "date_range": date_range,
        "follower_min": follower_min,
        "follower_max": follower_max,
        "interaction_min": interaction_min,
        "interaction_max": interaction_max,
        "size": size,
        "offset": offset,
    }
    _ = SearchPlan(
        filters={
            "industry_key": industry_key,
            "date_range": date_range,
            "follower_min": follower_min,
            "follower_max": follower_max,
            "interaction_min": interaction_min,
            "interaction_max": interaction_max,
        },
        sort={"key": sort, "order": order},
        limit=size,
        sql_params=params,
    )

    def run_query(where_query_clause: str) -> tuple[int, list[dict[str, Any]]]:
        rows = db.execute(
            text(
                f"""
            WITH scoped_notes AS (
                SELECT f.*
                FROM xhs_note_fact f
                LEFT JOIN xhs_note_industry_rel rel
                  ON rel.note_id = f.note_id
                 AND rel.industry_key = (:industry_key)::text
                WHERE f.author_id IS NOT NULL
                  AND f.author_id <> ''
                  AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                  AND ((:industry_key)::text IS NULL OR rel.note_id IS NOT NULL)
            ),
            author_stats AS (
                SELECT
                    n.author_id,
                    MAX(COALESCE(n.author_nickname, '')) AS author_nickname,
                    COUNT(*) AS matched_note_count,
                    MAX(COALESCE(n.author_fans_count, 0)) AS note_max_fans,
                    SUM(COALESCE(n.like_count, 0)) AS like_total,
                    SUM(COALESCE(n.comment_count, 0)) AS comment_total,
                    SUM(COALESCE(n.collection_count, 0)) AS collection_total,
                    SUM(COALESCE(n.share_count, 0)) AS share_total,
                    SUM(COALESCE(n.interaction_total, COALESCE(n.like_count,0)+COALESCE(n.comment_count,0)+COALESCE(n.collection_count,0)+COALESCE(n.share_count,0))) AS interaction_total,
                    MAX(COALESCE(n.updated_at, n.created_at)) AS latest_data_at
                FROM scoped_notes n
                WHERE {where_query_clause}
                GROUP BY n.author_id
            ),
            unique_anchor_nick AS (
                SELECT
                    nickname,
                    MIN(author_id) AS author_id
                FROM xhs_anchor_dim
                WHERE COALESCE(nickname, '') <> ''
                GROUP BY nickname
                HAVING COUNT(*) = 1
            )
            {cte_author_totals}
            SELECT
                s.author_id,
                s.author_nickname,
                COALESCE(NULLIF(COALESCE(a.fans_count, an.fans_count), 0), NULLIF(s.note_max_fans, 0), 0) AS followers,
                COALESCE(a.tag_list, an.tag_list, ARRAY[]::text[]) AS tag_list,
                COALESCE(
                    NULLIF(COALESCE(a.anchor_link, an.anchor_link), ''),
                    'https://www.xiaohongshu.com/user/profile/' || s.author_id
                ) AS creator_home_url,
                COALESCE(
                    NULLIF(COALESCE(a.total_note_count, an.total_note_count), 0),
                    s.matched_note_count
                )::bigint AS note_count,
                s.matched_note_count,
                (
                    LEAST(COALESCE(s.matched_note_count, 0), 120) * 8
                    + LEAST(COALESCE(s.interaction_total, 0) / 400, 600)
                    + CASE
                        WHEN s.latest_data_at >= now() - interval '3 day' THEN 30
                        WHEN s.latest_data_at >= now() - interval '7 day' THEN 18
                        WHEN s.latest_data_at >= now() - interval '30 day' THEN 6
                        ELSE 0
                    END
                )::bigint AS relevance_score,
                s.like_total,
                s.comment_total,
                s.collection_total,
                s.share_total,
                s.interaction_total,
                COALESCE(a.total_note_count, an.total_note_count, 0)::bigint AS anchor_total_note_count,
                s.latest_data_at,
                COUNT(*) OVER() AS total_count
            FROM author_stats s
            {join_author_totals}
            LEFT JOIN xhs_anchor_dim a ON a.author_id = s.author_id
            LEFT JOIN unique_anchor_nick aun ON aun.nickname = s.author_nickname
            LEFT JOIN xhs_anchor_dim an ON an.author_id = aun.author_id
            WHERE ((:follower_min)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, an.fans_count), 0), NULLIF(s.note_max_fans, 0), 0) >= (:follower_min)::bigint)
              AND ((:follower_max)::bigint IS NULL OR COALESCE(NULLIF(COALESCE(a.fans_count, an.fans_count), 0), NULLIF(s.note_max_fans, 0), 0) <= (:follower_max)::bigint)
              AND ((:interaction_min)::bigint IS NULL OR COALESCE(s.interaction_total, 0) >= (:interaction_min)::bigint)
              AND ((:interaction_max)::bigint IS NULL OR COALESCE(s.interaction_total, 0) <= (:interaction_max)::bigint)
            ORDER BY {order_clause}
            LIMIT :size OFFSET :offset
            """
            ),
            params,
        ).mappings().all()
        total = int(rows[0].get("total_count") or 0) if rows else 0
        return total, [dict(row) for row in rows]

    run_exact_first = bool(normalized_query)
    if run_exact_first:
        total, rows = run_query(exact_where_query)
        # 优先走 search_keyword 精准召回，只有命中不足时再触发全量模糊匹配。
        if 0 < total < max(size, 20):
            total, rows = run_query(fuzzy_where_query)
    else:
        total, rows = run_query(fuzzy_where_query)

    author_ids = [str(row["author_id"]) for row in rows if row.get("author_id")]
    author_totals: dict[str, dict[str, int]] = {}
    if author_ids:
        author_total_rows = db.execute(
            text(
                """
                SELECT
                    author_id,
                    COUNT(*)::bigint AS total_note_count,
                    MAX(COALESCE(author_fans_count, 0))::bigint AS note_max_fans,
                    SUM(
                        COALESCE(
                            interaction_total,
                            COALESCE(like_count, 0) + COALESCE(comment_count, 0) + COALESCE(collection_count, 0) + COALESCE(share_count, 0)
                        )
                    )::bigint AS total_interaction
                FROM xhs_note_fact
                WHERE author_id = ANY(:author_ids)
                GROUP BY author_id
                """
            ),
            {"author_ids": author_ids},
        ).mappings().all()
        author_totals = {
            str(row["author_id"]): {
                "total_note_count": int(row.get("total_note_count") or 0),
                "note_max_fans": int(row.get("note_max_fans") or 0),
                "total_interaction": int(row.get("total_interaction") or 0),
            }
            for row in author_total_rows
            if row.get("author_id")
        }

    notes: list[dict[str, Any]] = []
    if include_notes and author_ids:
        note_rows = db.execute(
            text(
                """
                SELECT
                    note_id, author_id, author_nickname, title, publish_time,
                    like_count, comment_count, collection_count, share_count
                FROM xhs_note_fact
                WHERE author_id = ANY(:author_ids)
                ORDER BY COALESCE(interaction_total, COALESCE(like_count,0)+COALESCE(comment_count,0)+COALESCE(collection_count,0)+COALESCE(share_count,0)) DESC,
                         publish_time DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"author_ids": author_ids, "limit": min(300, size * 10)},
        ).mappings().all()
        for row in note_rows:
            item = dict(row)
            if item.get("publish_time"):
                item["publish_time"] = item["publish_time"].isoformat()
            item["post_url"] = f"https://www.xiaohongshu.com/explore/{item['note_id']}"
            notes.append(item)

    latest_dt = max((row.get("latest_data_at") for row in rows if row.get("latest_data_at")), default=None)
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.pop("total_count", None)
        author_key = str(item.get("author_id") or "")
        totals = author_totals.get(author_key, {})
        fact_total_note_count = int(totals.get("total_note_count") or 0)
        anchor_total_note_count = int(item.get("anchor_total_note_count") or 0)
        effective_note_count = max(
            int(item.get("note_count") or 0),
            fact_total_note_count,
            anchor_total_note_count,
        )
        item["note_count"] = effective_note_count
        item["matched_note_count"] = int(item.get("matched_note_count") or 0)
        if int(item.get("followers") or 0) <= 0:
            fallback_followers = int(totals.get("note_max_fans") or 0)
            if fallback_followers > 0:
                item["followers"] = fallback_followers
        item["interaction_total"] = max(
            int(item.get("interaction_total") or 0),
            int(totals.get("total_interaction") or 0),
        )
        item.pop("anchor_total_note_count", None)
        if item.get("latest_data_at"):
            item["latest_data_at"] = item["latest_data_at"].isoformat()
        item["tags"] = item.pop("tag_list", []) or []
        items.append(item)

    summary = {
        "creator_count": total,
        "note_count": sum(int(item["note_count"]) for item in items),
        "like_total": sum(int(item["like_total"]) for item in items),
        "comment_total": sum(int(item["comment_total"]) for item in items),
        "collection_total": sum(int(item["collection_total"]) for item in items),
    }
    freshness = latest_dt.isoformat() if latest_dt else None

    return {
        "hit": total > 0,
        "summary": summary,
        "items": items,
        "notes": notes,
        "pagination": {
            "total": total,
            "page": page,
            "size": size,
            "has_more": offset + len(items) < total,
            "total_is_estimate": False,
        },
        "freshness": freshness,
    }


def query_brand_category_db_first(
    db: Session,
    *,
    query: str,
    mode: Literal["brand", "category"],
    industry: str | None,
    min_like: int,
    date_range: int,
    page: int,
    size: int,
    freshness_hours: int,
    sort: CategorySortKey = "stat",
    order: SortOrder = "desc",
    fast_pagination: bool = False,
) -> dict[str, Any]:
    size = _bounded_page_size(size)
    industry_key = resolve_industry_key(industry)
    if mode == "category" and not industry_key:
        industry_key = resolve_industry_key(query)
    normalized_query = query.strip()
    query_terms = _expand_query_terms(db, query, industry=industry)
    query_patterns = _to_like_patterns(query_terms)
    offset = max(page - 1, 0) * size
    order_clause = _category_order_clause(sort, order)
    text_match_clause = _build_text_match_exists_clause(alias="f")
    industry_priority_mode = mode == "category" and bool(industry_key)
    category_where_clause = (
        "true"
        if industry_priority_mode
        else """
            (
                (:industry_key)::text IS NOT NULL
                OR {text_match_clause}
                OR EXISTS (
                    SELECT 1
                    FROM unnest(CAST(:query_patterns AS text[])) AS qp(pattern)
                    WHERE EXISTS (
                        SELECT 1
                        FROM xhs_industry_keyword_dim ik
                        WHERE ik.keyword ILIKE qp.pattern
                          AND ik.keyword = f.search_keyword
                    )
                )
            )
        """.format(text_match_clause=text_match_clause)
    )

    def run_query(
        force_industry_only: bool,
        exact_keyword_only: bool,
        fast_page_query: bool,
    ) -> tuple[int, list[dict[str, Any]], bool]:
        if exact_keyword_only:
            brand_match_clause = """
                EXISTS (
                    SELECT 1
                    FROM xhs_note_brand_rel rel
                    LEFT JOIN xhs_brand_alias_dim alias ON alias.brand_name = rel.brand_name
                    WHERE rel.note_id = f.note_id
                      AND (
                            rel.brand_name = ANY(CAST(:query_terms AS text[]))
                         OR COALESCE(alias.alias, '') = ANY(CAST(:query_terms AS text[]))
                      )
                )
            """
            category_match_clause = (
                "true"
                if industry_priority_mode
                else "COALESCE(f.search_keyword, '') = ANY(CAST(:query_terms AS text[]))"
            )
        else:
            brand_match_clause = """
                EXISTS (
                    SELECT 1
                    FROM xhs_note_brand_rel rel
                    LEFT JOIN xhs_brand_alias_dim alias ON alias.brand_name = rel.brand_name
                    WHERE rel.note_id = f.note_id
                      AND EXISTS (
                          SELECT 1
                          FROM unnest(CAST(:query_patterns AS text[])) AS qp(pattern)
                          WHERE rel.brand_name ILIKE qp.pattern
                             OR COALESCE(alias.alias, '') ILIKE qp.pattern
                      )
                )
            """
            category_match_clause = category_where_clause

        where_mode = """
            (
                (:force_industry_only)::boolean = true
                OR
                (
                    ((:mode)::text = 'brand' AND ({brand_match_clause}))
                    OR
                    (
                        (:mode)::text = 'category'
                        AND ({category_match_clause})
                    )
                )
            )
        """.format(
            brand_match_clause=brand_match_clause,
            category_match_clause=category_match_clause,
        )
        match_score_expr = (
            "0"
            if industry_priority_mode or exact_keyword_only
            else """
            CASE
                WHEN (:query_blank)::boolean = true THEN 0
                WHEN EXISTS (
                    SELECT 1
                    FROM unnest(CAST(:query_patterns AS text[])) AS qp(pattern)
                    WHERE COALESCE(f.search_keyword, '') ILIKE qp.pattern
                ) THEN 3
                WHEN COALESCE(f.search_keyword, '') = ANY(CAST(:query_terms AS text[])) THEN 2
                WHEN EXISTS (
                    SELECT 1
                    FROM unnest(CAST(:query_patterns AS text[])) AS qp(pattern)
                    WHERE COALESCE(f.title, '') ILIKE qp.pattern
                       OR COALESCE(f.content, '') ILIKE qp.pattern
                       OR COALESCE(f.author_nickname, '') ILIKE qp.pattern
                ) THEN 1
                ELSE 0
            END
        """
        )
        order_by_clause = order_clause if industry_priority_mode or exact_keyword_only else f"match_score DESC, {order_clause}"
        params = {
            "query_patterns": query_patterns or ([f"%{query.strip()}%"] if query.strip() else ["%%"]),
            "query_terms": query_terms or [query.strip()],
            "query_blank": query.strip() == "",
            "mode": mode,
            "min_like": min_like,
            "date_range": date_range,
            "industry_key": industry_key,
            "size": size,
            "offset": offset,
            "force_industry_only": force_industry_only,
            "query_limit": size + 1 if fast_page_query else size,
        }

        result_rows = db.execute(
            text(
                f"""
                SELECT
                    f.note_id,
                    f.title,
                    f.author_id,
                    f.author_nickname,
                    f.search_keyword,
                    COALESCE(f.like_count, 0) AS like_count,
                    COALESCE(f.comment_count, 0) AS comment_count,
                    COALESCE(f.collection_count, 0) AS collection_count,
                    COALESCE(f.share_count, 0) AS share_count,
                    COALESCE(f.read_count, 0) AS read_count,
                    COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0)) AS interaction_total,
                    {match_score_expr} AS match_score,
                    COALESCE(f.publish_time, f.updated_at, f.created_at) AS publish_time,
                    COALESCE(f.updated_at, f.created_at) AS latest_data_at
                FROM xhs_note_fact f
                WHERE COALESCE(f.like_count, 0) >= :min_like
                  AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                  AND {where_mode}
                  AND (
                        (:industry_key)::text IS NULL
                     OR EXISTS (
                            SELECT 1
                            FROM xhs_note_industry_rel nir
                            WHERE nir.note_id = f.note_id
                              AND nir.industry_key = (:industry_key)::text
                        )
                  )
                ORDER BY {order_by_clause}
                LIMIT :query_limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total_count = int(
            db.execute(
                text(
                    f"""
                    SELECT COUNT(*)::bigint AS total_count
                    FROM xhs_note_fact f
                    WHERE COALESCE(f.like_count, 0) >= :min_like
                      AND COALESCE(f.publish_time, f.updated_at, f.created_at) >= now() - ((:date_range)::text || ' day')::interval
                      AND {where_mode}
                      AND (
                            (:industry_key)::text IS NULL
                         OR EXISTS (
                                SELECT 1
                                FROM xhs_note_industry_rel nir
                                WHERE nir.note_id = f.note_id
                                  AND nir.industry_key = (:industry_key)::text
                            )
                      )
                    """
                ),
                params,
            ).scalar()
            or 0
        )
        if fast_page_query:
            has_more = len(result_rows) > size
            page_rows = result_rows[:size]
        else:
            has_more = False
            page_rows = result_rows
        normalized_rows = []
        for row in page_rows:
            item = dict(row)
            normalized_rows.append(item)
        return total_count, normalized_rows, (has_more or (offset + len(normalized_rows) < total_count))

    run_exact_first = bool(normalized_query)
    if run_exact_first:
        if fast_pagination:
            total, rows, has_more = run_query(
                force_industry_only=False,
                exact_keyword_only=True,
                fast_page_query=True,
            )
            if not rows:
                total, rows, has_more = run_query(
                    force_industry_only=False,
                    exact_keyword_only=False,
                    fast_page_query=True,
                )
        else:
            total, rows, has_more = run_query(
                force_industry_only=False,
                exact_keyword_only=True,
                fast_page_query=False,
            )
            if 0 < total < max(size, 20):
                total, rows, has_more = run_query(
                    force_industry_only=False,
                    exact_keyword_only=False,
                    fast_page_query=False,
                )
    else:
        total, rows, has_more = run_query(
            force_industry_only=False,
            exact_keyword_only=False,
            fast_page_query=fast_pagination,
        )
    # 行业入口命中不足时自动退宽召回，避免“有数据但搜空”。
    if industry_key and mode == "category" and ((fast_pagination and not rows) or (not fast_pagination and total < 20)):
        total, rows, has_more = run_query(
            force_industry_only=True,
            exact_keyword_only=False,
            fast_page_query=fast_pagination,
        )

    latest_dt = max((row.get("latest_data_at") for row in rows if row.get("latest_data_at")), default=None)
    items: list[dict[str, Any]] = []
    creators: set[str] = set()
    for row in rows:
        item = dict(row)
        creators.add(str(item.get("author_id") or "").strip())
        if item.get("publish_time"):
            item["publish_time"] = item["publish_time"].isoformat()
        if item.get("latest_data_at"):
            item["latest_data_at"] = item["latest_data_at"].isoformat()
        item["post_url"] = f"https://www.xiaohongshu.com/explore/{item['note_id']}"
        items.append(item)

    summary = {
        "note_count": total,
        "creator_count": len([c for c in creators if c]),
        "like_total": sum(int(item["like_count"]) for item in items),
        "comment_total": sum(int(item["comment_count"]) for item in items),
        "collection_total": sum(int(item["collection_count"]) for item in items),
    }
    freshness = latest_dt.isoformat() if latest_dt else None

    return {
        "hit": total > 0,
        "summary": summary,
        "items": items,
        "pagination": {
            "total": total,
            "page": page,
            "size": size,
            "has_more": has_more,
            "total_is_estimate": fast_pagination,
        },
        "freshness": freshness,
    }
