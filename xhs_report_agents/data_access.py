from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from collections import Counter, defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine

from .schemas import (
    AuthorEvidence,
    CommentEvidence,
    CompetitorMetric,
    DataQuality,
    EvidencePack,
    MetricBlock,
    NoteEvidence,
)


def create_readonly_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=45000"},
    )


class DataScoutAgent:
    def __init__(self, engine: Engine):
        self.engine = engine

    def build_evidence_pack(
        self,
        *,
        brand: str,
        category: str,
        core_products: list[str],
        competitor_brands: list[str],
        window_days: int,
        max_notes: int = 1000,
        max_comments: int = 500,
        enable_text_fallback: bool = False,
    ) -> EvidencePack:
        terms = _expand_brand_terms(brand, core_products)
        with self.engine.begin() as conn:
            metrics = self._fetch_full_metrics(conn, terms=terms, window_days=window_days)
            rows = self._fetch_stratified_notes(
                conn,
                terms=terms,
                window_days=window_days,
                limit=max_notes,
                enable_text_fallback=enable_text_fallback,
            )
            notes = [_note_from_row(row, idx + 1) for idx, row in enumerate(rows[:80])]
            top_authors = self._fetch_top_authors(conn, terms=terms, window_days=window_days)
            keywords = self._fetch_keywords(conn, terms=terms, window_days=window_days)
            topics = self._fetch_topics(conn, terms=terms, window_days=window_days)
            trends = self._fetch_weekly_trend(conn, terms=terms, window_days=window_days)
            coverage = self._fetch_coverage_diagnostics(conn, terms=terms, window_days=window_days)
            comments = self._fetch_comments(conn, [r["note_id"] for r in rows[:250]], limit=max_comments)
            competitor_metrics = []
            for comp in competitor_brands:
                comp_terms = _expand_brand_terms(comp, [])
                competitor_metrics.append(
                    CompetitorMetric(
                        brand=comp,
                        aliases=[],
                        metrics=self._fetch_full_metrics(conn, terms=comp_terms, window_days=window_days),
                    )
                )
        quality = _data_quality(metrics, comments, len(rows))
        return EvidencePack(
            brand=brand,
            category=category,
            core_products=core_products,
            aliases=terms,
            competitors=competitor_brands,
            window_days=window_days,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            core_metrics=metrics,
            competitor_metrics=competitor_metrics,
            top_notes=notes,
            top_authors=top_authors,
            keyword_signals=[*keywords, *topics, *trends, *coverage],
            comment_signals=comments,
            data_quality=quality,
        )

    def _fetch_coverage_diagnostics(self, conn, *, terms: list[str], window_days: int) -> list[dict[str, Any]]:
        rows = []
        for days in (30, 90, 180, 365):
            row = conn.execute(
                text(
                    f"""
                    WITH ids AS MATERIALIZED ({_ids_cte_body()})
                    SELECT COUNT(*) AS note_count,
                           COUNT(DISTINCT NULLIF(f.author_id, '')) AS author_count,
                           COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                    FROM ids
                    JOIN xhs_note_fact f ON f.note_id = ids.note_id
                    WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                    """
                ),
                _term_params(terms, days),
            ).mappings().first()
            rows.append(
                {
                    "type": "coverage_window",
                    "window_days": days,
                    "note_count": int((row or {}).get("note_count") or 0),
                    "author_count": int((row or {}).get("author_count") or 0),
                    "interaction_total": int((row or {}).get("interaction_total") or 0),
                }
            )
        total = conn.execute(
            text("SELECT COUNT(*) AS note_count FROM xhs_note_fact")
        ).mappings().first()
        rows.append(
            {
                "type": "coverage_database",
                "window_days": window_days,
                "note_count": int((total or {}).get("note_count") or 0),
                "expanded_term_count": len(terms),
                "expanded_terms": terms[:40],
            }
        )
        return rows

    def _fetch_full_metrics(self, conn, *, terms: list[str], window_days: int) -> MetricBlock:
        params = _term_params(terms, window_days)
        row = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT COUNT(*) AS note_count,
                       COUNT(DISTINCT NULLIF(f.author_id, '')) AS author_count,
                       COALESCE(SUM(COALESCE(f.like_count, 0)), 0) AS like_total,
                       COALESCE(SUM(COALESCE(f.comment_count, 0)), 0) AS comment_total,
                       COALESCE(SUM(COALESCE(f.collection_count, 0)), 0) AS collection_total,
                       COALESCE(SUM(COALESCE(f.share_count, 0)), 0) AS share_total,
                       COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                """
            ),
            params,
        ).mappings().first()
        if not row:
            return MetricBlock()
        note_count = int(row["note_count"] or 0)
        collection_total = int(row["collection_total"] or 0)
        interaction_total = int(row["interaction_total"] or 0)
        return MetricBlock(
            note_count=note_count,
            author_count=int(row["author_count"] or 0),
            like_total=int(row["like_total"] or 0),
            comment_total=int(row["comment_total"] or 0),
            collection_total=collection_total,
            share_total=int(row["share_total"] or 0),
            interaction_total=interaction_total,
            avg_interaction=round(interaction_total / note_count, 2) if note_count else 0.0,
            avg_collection=round(collection_total / note_count, 2) if note_count else 0.0,
        )

    def _fetch_notes(
        self,
        conn,
        *,
        terms: list[str],
        window_days: int,
        limit: int,
        enable_text_fallback: bool,
    ) -> list[dict[str, Any]]:
        fast_rows = self._fetch_notes_fast(conn, terms=terms, window_days=window_days, limit=limit)
        if len(fast_rows) >= limit or not enable_text_fallback:
            return fast_rows
        seen = {str(r.get("note_id") or "") for r in fast_rows}
        remaining = max(limit - len(fast_rows), 1)
        fallback_rows = self._fetch_notes_text_safe(terms=terms, window_days=window_days, limit=min(remaining, 120))
        merged = [*fast_rows]
        for row in fallback_rows:
            note_id = str(row.get("note_id") or "")
            if note_id not in seen:
                merged.append(row)
                seen.add(note_id)
        return merged[:limit]

    def _fetch_stratified_notes(
        self,
        conn,
        *,
        terms: list[str],
        window_days: int,
        limit: int,
        enable_text_fallback: bool,
    ) -> list[dict[str, Any]]:
        target = max(limit, 1)
        groups = [
            ("top_interaction", "interaction_total DESC, active_time DESC"),
            ("high_collection", "collection_count DESC, interaction_total DESC, active_time DESC"),
            ("high_comment", "comment_count DESC, interaction_total DESC, active_time DESC"),
            ("high_share", "share_count DESC, interaction_total DESC, active_time DESC"),
            ("recent", "active_time DESC, interaction_total DESC"),
        ]
        per_group = min(max(target // len(groups), 24), 240)
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group, order_by in groups:
            for row in self._fetch_notes_ordered(conn, terms=terms, window_days=window_days, limit=per_group, order_by=order_by):
                note_id = str(row.get("note_id") or "")
                if note_id and note_id not in seen:
                    row["sample_group"] = group
                    merged.append(row)
                    seen.add(note_id)
                if len(merged) >= target:
                    return merged
        if len(merged) < target:
            for row in self._fetch_notes(conn, terms=terms, window_days=window_days, limit=target, enable_text_fallback=enable_text_fallback):
                note_id = str(row.get("note_id") or "")
                if note_id and note_id not in seen:
                    row.setdefault("sample_group", "supplement")
                    merged.append(row)
                    seen.add(note_id)
                if len(merged) >= target:
                    break
        return merged

    def _fetch_notes_ordered(self, conn, *, terms: list[str], window_days: int, limit: int, order_by: str) -> list[dict[str, Any]]:
        params = _term_params(terms, window_days)
        params.update({"limit": limit})
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT f.note_id, f.title, f.content, f.post_url, f.publish_time, f.tags,
                       f.author_id, f.author_nickname, COALESCE(f.author_fans_count, 0) AS author_fans_count,
                       COALESCE(f.like_count, 0) AS like_count,
                       COALESCE(f.comment_count, 0) AS comment_count,
                       COALESCE(f.collection_count, 0) AS collection_count,
                       COALESCE(f.share_count, 0) AS share_count,
                       COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0)) AS interaction_total,
                       COALESCE(f.search_keyword, '') AS search_keyword,
                       COALESCE(f.publish_time, f.created_at) AS active_time
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                ORDER BY {order_by}
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(r) for r in rows]

    def _fetch_notes_text_safe(self, *, terms: list[str], window_days: int, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        try:
            with self.engine.begin() as fallback_conn:
                fallback_conn.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                return self._fetch_notes_text(fallback_conn, terms=terms, window_days=window_days, limit=limit)
        except OperationalError as exc:
            if "QueryCanceled" in str(exc) or "statement timeout" in str(exc):
                return []
            raise

    def _fetch_notes_fast(self, conn, *, terms: list[str], window_days: int, limit: int) -> list[dict[str, Any]]:
        params = _term_params(terms, window_days)
        params.update({"limit": limit})
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT f.note_id, f.title, f.content, f.post_url, f.publish_time, f.tags,
                       f.author_id, f.author_nickname, COALESCE(f.author_fans_count, 0) AS author_fans_count,
                       COALESCE(f.like_count, 0) AS like_count,
                       COALESCE(f.comment_count, 0) AS comment_count,
                       COALESCE(f.collection_count, 0) AS collection_count,
                       COALESCE(f.share_count, 0) AS share_count,
                       COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0)) AS interaction_total,
                       COALESCE(f.search_keyword, '') AS search_keyword,
                       COALESCE(f.publish_time, f.created_at) AS active_time
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                ORDER BY interaction_total DESC, active_time DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(r) for r in rows]

    def _fetch_top_authors(self, conn, *, terms: list[str], window_days: int) -> list[AuthorEvidence]:
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT f.author_id,
                       COALESCE(NULLIF(MAX(f.author_nickname), ''), '') AS author_nickname,
                       COUNT(*) AS note_count,
                       COALESCE(MAX(COALESCE(f.author_fans_count, 0)), 0) AS fans_count,
                       COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                  AND COALESCE(f.author_id, '') <> ''
                GROUP BY f.author_id
                ORDER BY interaction_total DESC, note_count DESC
                LIMIT 30
                """
            ),
            _term_params(terms, window_days),
        ).mappings().all()
        return [
            AuthorEvidence(
                evidence_id=f"A{i+1}",
                author_id=str(r["author_id"] or ""),
                author_nickname=str(r["author_nickname"] or ""),
                note_count=int(r["note_count"] or 0),
                fans_count=int(r["fans_count"] or 0),
                interaction_total=int(r["interaction_total"] or 0),
            )
            for i, r in enumerate(rows)
        ]

    def _fetch_keywords(self, conn, *, terms: list[str], window_days: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT COALESCE(NULLIF(f.search_keyword, ''), '未标注') AS search_keyword,
                       COUNT(*) AS note_count,
                       COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                GROUP BY 1
                ORDER BY note_count DESC, interaction_total DESC
                LIMIT 40
                """
            ),
            _term_params(terms, window_days),
        ).mappings().all()
        return [
            {
                "type": "keyword",
                "search_keyword": str(r["search_keyword"] or "未标注"),
                "note_count": int(r["note_count"] or 0),
                "interaction_total": int(r["interaction_total"] or 0),
            }
            for r in rows
        ]

    def _fetch_weekly_trend(self, conn, *, terms: list[str], window_days: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT to_char(date_trunc('week', COALESCE(f.publish_time, f.created_at)), 'YYYY-MM-DD') AS week_start,
                       COUNT(*) AS note_count,
                       COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                GROUP BY 1
                ORDER BY 1
                """
            ),
            _term_params(terms, window_days),
        ).mappings().all()
        return [
            {
                "type": "weekly_trend",
                "week_start": str(r["week_start"] or ""),
                "note_count": int(r["note_count"] or 0),
                "interaction_total": int(r["interaction_total"] or 0),
            }
            for r in rows
        ]

    def _fetch_topics(self, conn, *, terms: list[str], window_days: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            text(
                f"""
                WITH ids AS MATERIALIZED ({_ids_cte_body()})
                SELECT tag AS topic,
                       COUNT(*) AS note_count,
                       COALESCE(SUM(COALESCE(f.interaction_total, COALESCE(f.like_count,0)+COALESCE(f.comment_count,0)+COALESCE(f.collection_count,0)+COALESCE(f.share_count,0))), 0) AS interaction_total
                FROM ids
                JOIN xhs_note_fact f ON f.note_id = ids.note_id
                CROSS JOIN LATERAL unnest(COALESCE(f.tags, ARRAY[]::text[])) AS tag
                WHERE date(COALESCE(f.publish_time, f.created_at)) >= current_date - (:days - 1) * interval '1 day'
                  AND COALESCE(tag, '') <> ''
                GROUP BY tag
                ORDER BY note_count DESC, interaction_total DESC
                LIMIT 36
                """
            ),
            _term_params(terms, window_days),
        ).mappings().all()
        return [
            {
                "type": "topic",
                "name": str(r["topic"] or ""),
                "note_count": int(r["note_count"] or 0),
                "interaction_total": int(r["interaction_total"] or 0),
            }
            for r in rows
        ]

    def _fetch_notes_text(self, conn, *, terms: list[str], window_days: int, limit: int) -> list[dict[str, Any]]:
        where, params = _like_clause(terms)
        params.update({"days": window_days, "limit": limit, "candidate_limit": max(limit * 5, 200)})
        sql = text(
            f"""
            WITH matched AS MATERIALIZED (
                SELECT note_id, title, content, post_url, publish_time, tags,
                       author_id, author_nickname, COALESCE(author_fans_count, 0) AS author_fans_count,
                       COALESCE(like_count, 0) AS like_count,
                       COALESCE(comment_count, 0) AS comment_count,
                       COALESCE(collection_count, 0) AS collection_count,
                       COALESCE(share_count, 0) AS share_count,
                       COALESCE(interaction_total, COALESCE(like_count,0)+COALESCE(comment_count,0)+COALESCE(collection_count,0)+COALESCE(share_count,0)) AS interaction_total,
                       COALESCE(search_keyword, '') AS search_keyword,
                       COALESCE(publish_time, created_at) AS active_time
                FROM xhs_note_fact
                WHERE date(COALESCE(publish_time, created_at)) >= current_date - (:days - 1) * interval '1 day'
                  AND ({where})
                LIMIT :candidate_limit
            )
            SELECT *
            FROM matched
            ORDER BY interaction_total DESC, active_time DESC
            LIMIT :limit
            """
        )
        return [dict(r) for r in conn.execute(sql, params).mappings().all()]

    def _fetch_comments(self, conn, note_ids: list[str], *, limit: int) -> list[CommentEvidence]:
        if not note_ids:
            return []
        rows = conn.execute(
            text(
                """
                SELECT parent_note_id, comment_text, COALESCE(comment_likes, 0) AS comment_likes, comment_sentiment
                FROM xhs_comment_fact
                WHERE parent_note_id = ANY(CAST(:note_ids AS text[]))
                ORDER BY COALESCE(comment_likes, 0) DESC, created_at DESC
                LIMIT :limit
                """
            ),
            {"note_ids": note_ids, "limit": limit},
        ).mappings().all()
        return [
            CommentEvidence(
                evidence_id=f"C{i+1}",
                parent_note_id=str(r["parent_note_id"]),
                comment_text=_truncate(str(r["comment_text"] or ""), 180),
                comment_likes=int(r["comment_likes"] or 0),
                comment_sentiment=r["comment_sentiment"],
            )
            for i, r in enumerate(rows)
        ]


def _clean_terms(values: list[str]) -> list[str]:
    out = []
    for value in values:
        v = value.strip()
        if v and v.lower() not in {x.lower() for x in out}:
            out.append(v)
    return out


BRAND_LEXICON: dict[str, list[str]] = {
    "兰蔻": ["lancome", "小黑瓶", "菁纯", "粉水", "极光水", "小白管", "持妆粉底液", "菁纯眼霜", "塑颜", "超修", "安瓶精华", "菁纯唇膏", "菁纯粉底", "兰蔻防晒"],
    "雅诗兰黛": ["esteelauder", "小棕瓶", "白金", "胶原霜", "沁水粉底", "dw粉底", "樱花水", "智妍"],
    "欧莱雅": ["loreal", "欧莱雅紫熨斗", "小蜜罐", "玻色因", "金致臻颜", "复颜"],
    "修丽可": ["skinceuticals", "色修", "ce精华", "紫米精华", "age面霜", "植萃"],
    "ysl": ["圣罗兰", "ysl", "小金条", "黑管", "粉气垫", "恒久粉底"],
}


def _expand_brand_terms(brand: str, aliases: list[str]) -> list[str]:
    seeds = [brand, *aliases]
    normalized = {brand.lower(), *[item.lower() for item in aliases]}
    for key, terms in BRAND_LEXICON.items():
        if key.lower() in normalized or any(item.lower() in normalized for item in terms):
            seeds.extend(terms)
    return _clean_terms(seeds)


def _like_clause(terms: list[str]) -> tuple[str, dict[str, Any]]:
    parts = []
    params: dict[str, Any] = {}
    blob = "lower(concat_ws(' ', coalesce(title,''), coalesce(content,''), coalesce(array_to_string(tags, ' '),''), coalesce(search_keyword,'')))"
    for idx, term in enumerate(terms):
        key = f"term_{idx}"
        parts.append(f"{blob} LIKE :{key}")
        params[key] = f"%{term.lower()}%"
    if not parts:
        parts.append("false")
    return " OR ".join(parts), params


def _term_params(terms: list[str], window_days: int) -> dict[str, Any]:
    return {
        "lower_terms": [t.lower() for t in terms],
        "raw_terms": terms,
        "days": window_days,
    }


def _ids_cte_body() -> str:
    return """
        SELECT note_id
        FROM xhs_note_term_rel
        WHERE lower(term) = ANY(CAST(:lower_terms AS text[]))
        UNION
        SELECT note_id
        FROM xhs_note_fact
        WHERE search_keyword = ANY(CAST(:raw_terms AS text[]))
          AND date(COALESCE(publish_time, created_at)) >= current_date - (:days - 1) * interval '1 day'
        UNION
        SELECT note_id
        FROM xhs_note_brand_rel
        WHERE lower(brand_name) = ANY(CAST(:lower_terms AS text[]))
           OR lower(matched_keyword) = ANY(CAST(:lower_terms AS text[]))
    """


def _note_from_row(row: dict[str, Any], idx: int) -> NoteEvidence:
    content = re.sub(r"\s+", " ", str(row.get("content") or "")).strip()
    return NoteEvidence(
        evidence_id=f"N{idx}",
        note_id=str(row.get("note_id") or ""),
        sample_group=str(row.get("sample_group") or "top_interaction"),
        title=str(row.get("title") or ""),
        content_excerpt=_truncate(content, 220),
        author_nickname=str(row.get("author_nickname") or ""),
        publish_time=row.get("publish_time").isoformat() if row.get("publish_time") else None,
        post_url=str(row.get("post_url") or ""),
        like_count=int(row.get("like_count") or 0),
        comment_count=int(row.get("comment_count") or 0),
        collection_count=int(row.get("collection_count") or 0),
        share_count=int(row.get("share_count") or 0),
        interaction_total=int(row.get("interaction_total") or 0),
        tags=list(row.get("tags") or []),
    )


def _metrics(rows: list[dict[str, Any]]) -> MetricBlock:
    note_count = len(rows)
    authors = {str(r.get("author_id") or "") for r in rows if r.get("author_id")}
    like_total = sum(int(r.get("like_count") or 0) for r in rows)
    comment_total = sum(int(r.get("comment_count") or 0) for r in rows)
    collection_total = sum(int(r.get("collection_count") or 0) for r in rows)
    share_total = sum(int(r.get("share_count") or 0) for r in rows)
    interaction_total = sum(int(r.get("interaction_total") or 0) for r in rows)
    return MetricBlock(
        note_count=note_count,
        author_count=len(authors),
        like_total=like_total,
        comment_total=comment_total,
        collection_total=collection_total,
        share_total=share_total,
        interaction_total=interaction_total,
        avg_interaction=round(interaction_total / note_count, 2) if note_count else 0.0,
        avg_collection=round(collection_total / note_count, 2) if note_count else 0.0,
    )


def _authors_from_rows(rows: list[dict[str, Any]]) -> list[AuthorEvidence]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        author_id = str(row.get("author_id") or "")
        if not author_id:
            continue
        item = grouped.setdefault(
            author_id,
            {
                "author_id": author_id,
                "author_nickname": str(row.get("author_nickname") or ""),
                "note_count": 0,
                "fans_count": 0,
                "interaction_total": 0,
            },
        )
        item["note_count"] += 1
        item["fans_count"] = max(int(item["fans_count"] or 0), int(row.get("author_fans_count") or 0))
        item["interaction_total"] += int(row.get("interaction_total") or 0)
    ranked = sorted(grouped.values(), key=lambda x: (x["interaction_total"], x["note_count"]), reverse=True)[:30]
    return [AuthorEvidence(evidence_id=f"A{i+1}", **item) for i, item in enumerate(ranked)]


def _keywords_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    interactions: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        keyword = str(row.get("search_keyword") or "").strip()
        if not keyword:
            continue
        counts[keyword] += 1
        interactions[keyword] += int(row.get("interaction_total") or 0)
    return [
        {"search_keyword": keyword, "note_count": count, "interaction_total": interactions[keyword]}
        for keyword, count in counts.most_common(40)
    ]


def _data_quality(metrics: MetricBlock, comments: list[CommentEvidence], row_count: int) -> DataQuality:
    reasons: list[str] = []
    notes: list[str] = []
    population_count = metrics.note_count or row_count
    if population_count < 30:
        reasons.append("sample_size_low")
        notes.append("品牌样本量低于 30 条，趋势和评分置信度需要降低。")
    if metrics.note_count and metrics.interaction_total == 0:
        reasons.append("metrics_sparse")
        notes.append("样本互动、点赞、评论、收藏字段大量为 0，可能是详情数据未补齐，不能解读为真实低互动。")
    elif metrics.note_count and (metrics.like_total + metrics.comment_total + metrics.collection_total) == 0:
        reasons.append("metrics_sparse")
        notes.append("核心互动字段为空或为 0，报告会优先使用声量、文本和作者结构。")
    if len(comments) < 20:
        reasons.append("comments_insufficient")
        notes.append("评论样本不足，受众洞察主要来自笔记文本和内容场景。")
    status = "ok" if not reasons else ("limited" if "metrics_sparse" in reasons or "sample_size_low" in reasons else "warning")
    return DataQuality(status=status, reasons=reasons, notes=notes)


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
