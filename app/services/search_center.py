from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.industry_catalog import ensure_industry_tables, resolve_industry_key
from app.services.search_intent import split_intent_terms

SearchType = Literal["influencer", "brand_category"]
SearchStatus = Literal["pending", "running", "ready", "failed"]

CategorySortKey = Literal["stat", "like", "read", "comments"]
CreatorSortKey = Literal["followers", "notes", "sumStat"]
SortOrder = Literal["asc", "desc"]

_search_bootstrap_done = False

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
    _seed_search_synonyms(db)
    db.commit()
    _search_bootstrap_done = True


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


def evaluate_result_health(
    result: dict[str, Any],
    *,
    min_results: int,
    stale_hours: int,
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
        if age_hours > max(1, stale_hours):
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
    stale_hours: int,
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
    mapping = {
        "followers": "COALESCE(NULLIF(a.fans_count, 0), NULLIF(s.note_max_fans, 0), 0)",
        "notes": "s.matched_note_count",
        "sumStat": "s.interaction_total",
    }
    expr = mapping.get(sort, mapping["sumStat"])
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
    ensure_search_tables(db)
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
    ensure_search_tables(db)
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
        mark_search_job_ready(
            db,
            job_id=job_id,
            response_payload={"crawl_batch_id": crawl_batch_id, "row_count": int(crawl.get("row_count") or 0)},
        )
    elif crawl_status == "failed":
        mark_search_job_failed(db, job_id=job_id, error_msg=str(crawl.get("error_msg") or "crawl failed"))
    return get_search_job(db, job_id)


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
    sort: CreatorSortKey = "followers",
    order: SortOrder = "desc",
) -> dict[str, Any]:
    ensure_search_tables(db)
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
        "GREATEST(COALESCE(at.total_note_count, 0), COALESCE(a.total_note_count, 0), COALESCE(s.matched_note_count, 0)) "
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

    where_query = """
        (
                :query = ''
             OR n.author_id = ANY(CAST(:query_terms AS text[]))
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
                WHERE {where_query}
                GROUP BY n.author_id
            )
            {cte_author_totals}
            SELECT
                s.author_id,
                s.author_nickname,
                COALESCE(NULLIF(a.fans_count, 0), NULLIF(s.note_max_fans, 0), 0) AS followers,
                COALESCE(a.tag_list, ARRAY[]::text[]) AS tag_list,
                COALESCE(
                    NULLIF(a.total_note_count, 0),
                    s.matched_note_count
                )::bigint AS note_count,
                s.matched_note_count,
                s.like_total,
                s.comment_total,
                s.collection_total,
                s.share_total,
                s.interaction_total,
                COALESCE(a.total_note_count, 0)::bigint AS anchor_total_note_count,
                s.latest_data_at,
                COUNT(*) OVER() AS total_count
            FROM author_stats s
            {join_author_totals}
            LEFT JOIN xhs_anchor_dim a ON a.author_id = s.author_id
            WHERE ((:follower_min)::bigint IS NULL OR COALESCE(NULLIF(a.fans_count, 0), NULLIF(s.note_max_fans, 0), 0) >= (:follower_min)::bigint)
              AND ((:follower_max)::bigint IS NULL OR COALESCE(NULLIF(a.fans_count, 0), NULLIF(s.note_max_fans, 0), 0) <= (:follower_max)::bigint)
              AND ((:interaction_min)::bigint IS NULL OR COALESCE(s.interaction_total, 0) >= (:interaction_min)::bigint)
              AND ((:interaction_max)::bigint IS NULL OR COALESCE(s.interaction_total, 0) <= (:interaction_max)::bigint)
            ORDER BY {order_clause}
            LIMIT :size OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    total = int(rows[0].get("total_count") or 0) if rows else 0

    author_ids = [str(row["author_id"]) for row in rows if row.get("author_id")]
    author_totals: dict[str, dict[str, int]] = {}
    if author_ids:
        author_total_rows = db.execute(
            text(
                """
                SELECT
                    author_id,
                    COUNT(*)::bigint AS total_note_count,
                    MAX(COALESCE(author_fans_count, 0))::bigint AS note_max_fans
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
            }
            for row in author_total_rows
            if row.get("author_id")
        }

    notes: list[dict[str, Any]] = []
    if author_ids:
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
) -> dict[str, Any]:
    ensure_search_tables(db)
    size = _bounded_page_size(size)
    industry_key = resolve_industry_key(industry)
    if mode == "category" and not industry_key:
        industry_key = resolve_industry_key(query)
    query_terms = _expand_query_terms(db, query, industry=industry)
    query_patterns = _to_like_patterns(query_terms)
    offset = max(page - 1, 0) * size
    order_clause = _category_order_clause(sort, order)
    text_match_clause = _build_text_match_exists_clause(alias="f")

    def run_query(force_industry_only: bool) -> tuple[int, list[dict[str, Any]]]:
        where_mode = """
            (
                (:force_industry_only)::boolean = true
                OR
                (
                    ((:mode)::text = 'brand' AND EXISTS (
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
                    ))
                    OR
                    (
                        (:mode)::text = 'category'
                        AND (
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
                    )
                )
            )
        """.format(text_match_clause=text_match_clause)
        match_score_expr = """
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
                    COALESCE(f.updated_at, f.created_at) AS latest_data_at,
                    COUNT(*) OVER() AS total_count
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
                ORDER BY match_score DESC, {order_clause}
                LIMIT :size OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total_count = int(result_rows[0].get("total_count") or 0) if result_rows else 0
        normalized_rows = []
        for row in result_rows:
            item = dict(row)
            item.pop("total_count", None)
            normalized_rows.append(item)
        return total_count, normalized_rows

    total, rows = run_query(force_industry_only=False)
    # 行业入口命中不足时自动退宽召回，避免“有数据但搜空”。
    if total < 20 and industry_key and mode == "category":
        total, rows = run_query(force_industry_only=True)

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
            "has_more": offset + len(items) < total,
        },
        "freshness": freshness,
    }
