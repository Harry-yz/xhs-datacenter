from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.beauty_taxonomy import BEAUTY_RECOMMENDED_EXPANSIONS


BEAUTY_BRAND_ALIASES: dict[str, dict[str, list[str]]] = {
    "兰蔻": {"primary": ["Lancome", "LANCOME"], "secondary": ["菁纯", "粉水"]},
    "雅诗兰黛": {"primary": ["Estee Lauder", "ESTEE LAUDER"], "secondary": ["小棕瓶"]},
    "欧莱雅": {"primary": ["L'Oreal", "LOREAL", "Loreal"], "secondary": []},
    "可复美": {"primary": [], "secondary": ["敷尔佳姐妹牌"]},
    "修丽可": {"primary": ["SkinCeuticals", "SC修丽可"], "secondary": []},
    "阿玛尼": {"primary": ["Armani", "GIORGIO ARMANI"], "secondary": ["GA"]},
    "YSL": {"primary": ["圣罗兰", "Yves Saint Laurent"], "secondary": []},
    "毛戈平": {"primary": ["MGP"], "secondary": []},
    "资生堂": {"primary": ["Shiseido", "SHISEIDO"], "secondary": []},
    "安热沙": {"primary": ["Anessa", "ANESSA"], "secondary": []},
}


def _brand_id(brand_name: str) -> str:
    digest = hashlib.md5(brand_name.encode("utf-8")).hexdigest()[:16]
    return f"brand_{digest}"


def _dedupe_preserve(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


@lru_cache(maxsize=1)
def build_brand_seed_items() -> list[dict[str, Any]]:
    configured_names = BEAUTY_RECOMMENDED_EXPANSIONS.get("品牌补充", [])
    items: list[dict[str, Any]] = []

    for brand_name in configured_names:
        alias_profile = BEAUTY_BRAND_ALIASES.get(brand_name, {"primary": [], "secondary": []})
        alias = _dedupe_preserve(
            [brand_name, *alias_profile.get("primary", []), *alias_profile.get("secondary", [])]
        )
        items.append(
            {
                "brand_id": _brand_id(brand_name),
                "brand_name": brand_name,
                "alias": alias,
                "primary_aliases": _dedupe_preserve(alias_profile.get("primary", [])),
                "secondary_aliases": _dedupe_preserve(alias_profile.get("secondary", [])),
                "industry": "美妆护肤",
                "description": f"{brand_name} 品牌字典种子",
            }
        )

    return items


def _find_keyword(text: str, keyword: str) -> int | None:
    if not text or not keyword:
        return None

    source = text.casefold()
    target = keyword.casefold()

    if re.fullmatch(r"[a-z0-9][a-z0-9 '&.-]*", target):
        pattern = rf"(?<![a-z0-9]){re.escape(target)}(?![a-z0-9])"
        match = re.search(pattern, source, flags=re.IGNORECASE)
        return match.start() if match else None

    index = source.find(target)
    if index >= 0:
        return index
    return None


def extract_brand_matches(
    *,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    segments = [
        ("title", title or ""),
        ("tags", " ".join(tags or [])),
        ("content", content or ""),
    ]

    matches_by_brand: dict[str, dict[str, Any]] = {}

    for source_name, segment in segments:
        if not segment.strip():
            continue

        for item in build_brand_seed_items():
            best_match: dict[str, Any] | None = None
            keyword_priority = [(item["brand_name"], 3)]
            keyword_priority.extend((keyword, 4) for keyword in item.get("primary_aliases", []))
            keyword_priority.extend((keyword, 1) for keyword in item.get("secondary_aliases", []))

            for keyword, priority in keyword_priority:
                position = _find_keyword(segment, keyword)
                if position is None:
                    continue

                candidate = {
                    "brand_id": item["brand_id"],
                    "brand_name": item["brand_name"],
                    "matched_keyword": keyword,
                    "match_source": source_name,
                    "match_position": position,
                    "match_priority": priority,
                }
                if best_match is None:
                    best_match = candidate
                    continue
                if candidate["match_priority"] > best_match["match_priority"]:
                    best_match = candidate
                    continue
                if (
                    candidate["match_priority"] == best_match["match_priority"]
                    and len(candidate["matched_keyword"]) > len(best_match["matched_keyword"])
                ):
                    best_match = candidate
                    continue
                if (
                    candidate["match_priority"] == best_match["match_priority"]
                    and len(candidate["matched_keyword"]) == len(best_match["matched_keyword"])
                    and candidate["match_position"] < best_match["match_position"]
                ):
                    best_match = candidate

            if best_match is None:
                continue

            current = matches_by_brand.get(item["brand_id"])
            if current is None:
                matches_by_brand[item["brand_id"]] = best_match
                continue
            if best_match["match_priority"] > current["match_priority"]:
                matches_by_brand[item["brand_id"]] = best_match
                continue
            if (
                best_match["match_priority"] == current["match_priority"]
                and len(best_match["matched_keyword"]) > len(current["matched_keyword"])
            ):
                matches_by_brand[item["brand_id"]] = best_match
                continue
            if (
                best_match["match_priority"] == current["match_priority"]
                and len(best_match["matched_keyword"]) == len(current["matched_keyword"])
                and best_match["match_position"] < current["match_position"]
            ):
                matches_by_brand[item["brand_id"]] = best_match

    items = sorted(
        matches_by_brand.values(),
        key=lambda item: (item["match_position"], item["brand_name"]),
    )
    for item in items:
        item.pop("match_priority", None)
    return items


def sync_brand_dictionary(db: Session) -> int:
    rows = 0
    for item in build_brand_seed_items():
        db.execute(
            text(
                """
                INSERT INTO xhs_brand_dim(
                    brand_id, brand_name, alias, industry, description, raw_payload
                )
                VALUES(
                    :brand_id, :brand_name, :alias, :industry, :description, CAST(:raw_payload AS jsonb)
                )
                ON CONFLICT (brand_id) DO UPDATE SET
                    brand_name = EXCLUDED.brand_name,
                    alias = EXCLUDED.alias,
                    industry = EXCLUDED.industry,
                    description = EXCLUDED.description,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = now()
                """
            ),
            {
                "brand_id": item["brand_id"],
                "brand_name": item["brand_name"],
                "alias": item["alias"],
                "industry": item["industry"],
                "description": item["description"],
                "raw_payload": (
                    '{"source":"beauty_brand_seed","brand_name":"%s"}' % item["brand_name"]
                ),
            },
        )
        rows += 1

    db.commit()
    return rows


def sync_note_brand_relations(
    db: Session,
    *,
    limit: int | None = None,
    min_like: int = 0,
    refresh_existing: bool = True,
    recent_hours: int | None = None,
) -> int:
    sql = """
        SELECT note_id, title, content, tags
        FROM xhs_note_fact
        WHERE COALESCE(like_count, 0) >= :min_like
    """

    if recent_hours and recent_hours > 0:
        sql += """
          AND COALESCE(updated_at, created_at) >= now() - (:recent_hours || ' hour')::interval
        """

    if not refresh_existing:
        sql += """
          AND NOT EXISTS (
                SELECT 1
                FROM xhs_note_brand_rel rel
                WHERE rel.note_id = xhs_note_fact.note_id
          )
        """

    sql += " ORDER BY COALESCE(like_count, 0) DESC, publish_time DESC NULLS LAST"

    if limit and limit > 0:
        sql += " LIMIT :limit"

    params: dict[str, Any] = {"min_like": min_like, "limit": limit, "recent_hours": recent_hours}
    rows = db.execute(text(sql), params).mappings().all()

    matched_rows = 0
    for row in rows:
        note_id = row["note_id"]
        if refresh_existing:
            db.execute(
                text("DELETE FROM xhs_note_brand_rel WHERE note_id = :note_id"),
                {"note_id": note_id},
            )

        matches = extract_brand_matches(
            title=row.get("title"),
            content=row.get("content"),
            tags=row.get("tags") or [],
        )
        for match in matches:
            db.execute(
                text(
                    """
                    INSERT INTO xhs_note_brand_rel(
                        note_id, brand_id, brand_name, matched_keyword, match_source, match_position
                    )
                    VALUES(
                        :note_id, :brand_id, :brand_name, :matched_keyword, :match_source, :match_position
                    )
                    ON CONFLICT (note_id, brand_id) DO UPDATE SET
                        matched_keyword = EXCLUDED.matched_keyword,
                        match_source = EXCLUDED.match_source,
                        match_position = EXCLUDED.match_position,
                        updated_at = now()
                    """
                ),
                {"note_id": note_id, **match},
            )
            matched_rows += 1

    db.commit()
    return matched_rows
