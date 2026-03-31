from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.beauty_taxonomy import BEAUTY_RECOMMENDED_EXPANSIONS, BEAUTY_TAXONOMY


def _serialize_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        keywords = row.get("keywords") or []
        items.append(
            {
                "category_name": row.get("category_name"),
                "group_name": row.get("group_name"),
                "keywords": keywords,
                "keyword_count": row.get("keyword_count") or len(keywords),
                "sort_no": row.get("sort_no"),
                "status": row.get("status"),
                "remark": row.get("remark"),
            }
        )
    return items


def build_beauty_catalog_payload(source: str = "config") -> dict[str, Any]:
    category_items = [
        {
            "category_name": category_name,
            "keywords": keywords,
            "keyword_count": len(keywords),
            "sort_no": index,
            "status": "enabled",
            "remark": "美妆核心分类",
        }
        for index, (category_name, keywords) in enumerate(BEAUTY_TAXONOMY.items(), start=1)
    ]
    recommendation_items = [
        {
            "group_name": group_name,
            "keywords": keywords,
            "keyword_count": len(keywords),
            "sort_no": index,
            "status": "enabled",
            "remark": "建议补充词",
        }
        for index, (group_name, keywords) in enumerate(BEAUTY_RECOMMENDED_EXPANSIONS.items(), start=1)
    ]
    return {
        "source": source,
        "category_count": len(category_items),
        "keyword_count": sum(item["keyword_count"] for item in category_items),
        "items": category_items,
        "recommended_expansion_group_count": len(recommendation_items),
        "recommended_expansions": recommendation_items,
    }


def sync_beauty_catalog(db: Session) -> dict[str, int]:
    category_count = 0
    keyword_count = 0

    for index, (category_name, keywords) in enumerate(BEAUTY_TAXONOMY.items(), start=1):
        db.execute(
            text(
                """
                INSERT INTO xhs_beauty_taxonomy_dim(
                    category_name, sort_no, status, keyword_count, keywords, remark
                )
                VALUES(
                    :category_name, :sort_no, 'enabled', :keyword_count, :keywords, :remark
                )
                ON CONFLICT(category_name) DO UPDATE SET
                    sort_no = EXCLUDED.sort_no,
                    status = EXCLUDED.status,
                    keyword_count = EXCLUDED.keyword_count,
                    keywords = EXCLUDED.keywords,
                    remark = EXCLUDED.remark,
                    updated_at = now()
                """
            ),
            {
                "category_name": category_name,
                "sort_no": index,
                "keyword_count": len(keywords),
                "keywords": keywords,
                "remark": "美妆核心分类",
            },
        )
        category_count += 1
        keyword_count += len(keywords)

    recommendation_group_count = 0
    recommendation_keyword_count = 0
    for index, (group_name, keywords) in enumerate(BEAUTY_RECOMMENDED_EXPANSIONS.items(), start=1):
        db.execute(
            text(
                """
                INSERT INTO xhs_beauty_recommendation_dim(
                    group_name, sort_no, status, keyword_count, keywords, remark
                )
                VALUES(
                    :group_name, :sort_no, 'enabled', :keyword_count, :keywords, :remark
                )
                ON CONFLICT(group_name) DO UPDATE SET
                    sort_no = EXCLUDED.sort_no,
                    status = EXCLUDED.status,
                    keyword_count = EXCLUDED.keyword_count,
                    keywords = EXCLUDED.keywords,
                    remark = EXCLUDED.remark,
                    updated_at = now()
                """
            ),
            {
                "group_name": group_name,
                "sort_no": index,
                "keyword_count": len(keywords),
                "keywords": keywords,
                "remark": "建议补充词",
            },
        )
        recommendation_group_count += 1
        recommendation_keyword_count += len(keywords)

    db.commit()
    return {
        "category_count": category_count,
        "keyword_count": keyword_count,
        "recommended_expansion_group_count": recommendation_group_count,
        "recommended_keyword_count": recommendation_keyword_count,
    }


def load_beauty_catalog(db: Session) -> dict[str, Any]:
    try:
        category_rows = db.execute(
            text(
                """
                SELECT category_name, sort_no, status, keyword_count, keywords, remark
                FROM xhs_beauty_taxonomy_dim
                WHERE status = 'enabled'
                ORDER BY sort_no ASC, category_name ASC
                """
            )
        ).mappings().all()
        recommendation_rows = db.execute(
            text(
                """
                SELECT group_name, sort_no, status, keyword_count, keywords, remark
                FROM xhs_beauty_recommendation_dim
                WHERE status = 'enabled'
                ORDER BY sort_no ASC, group_name ASC
                """
            )
        ).mappings().all()
    except Exception:
        return build_beauty_catalog_payload(source="config")

    if not category_rows:
        return build_beauty_catalog_payload(source="config")

    category_items = _serialize_items([dict(row) for row in category_rows])
    recommendation_items = _serialize_items([dict(row) for row in recommendation_rows])

    return {
        "source": "db",
        "category_count": len(category_items),
        "keyword_count": sum(item["keyword_count"] for item in category_items),
        "items": category_items,
        "recommended_expansion_group_count": len(recommendation_items),
        "recommended_expansions": recommendation_items,
    }
