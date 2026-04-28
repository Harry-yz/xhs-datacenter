from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db import SessionLocal

REPO_ROOT = Path(__file__).resolve().parents[1]

TARGET_BRAND = "伊丽莎白雅顿"
Q1_LABEL = "2026 Q1"
Q1_START = date(2026, 1, 1)
Q1_END = date(2026, 3, 31)
REAL_DATA_START = date(2026, 3, 17)

MOCK_OUTPUT = REPO_ROOT / "docs/reports/arden_brand_health_mock_q1_2026.html"
REAL_OUTPUT = REPO_ROOT / "docs/reports/arden_brand_health_real_q1_2026.html"

MUSIC_REGEX = r"(音乐剧|剧院|卡司|repo|返场|二刷|法扎|德扎|魅影|musical|broadway|west\s*end|伦敦西区)"
INTENT_REGEX = r"(求|同款|怎么买|哪里买|链接|购买|入手|种草|想买)"
ADVOCACY_REGEX = r"(回购|空瓶|爱用|无限回购|值得买)"
PREMIUM_REGEX = r"(vip|前排|香水|礼服|法餐|酒吧|沙龙香|精品咖啡)"
VOC_SAMPLE_GROUPS: list[dict[str, str]] = [
    {
        "name": "求同款 / 求链接",
        "pattern": r"(求|链接|同款|怎么买|哪里买)",
        "description": "直接出现求链接、求同款和购买路径咨询，属于最强的显性转化信号。",
    },
    {
        "name": "种草 / 想买",
        "pattern": r"(种草|想买|想入|被安利|被种草)",
        "description": "表达被打动、被安利和想入手，说明内容已经完成初步种草。",
    },
    {
        "name": "回购 / 爱用",
        "pattern": r"(回购|爱用|空瓶|值得买|无限回购)",
        "description": "出现爱用、空瓶和回购表达，说明品牌已有稳定的价值背书。",
    },
]

BRAND_PATTERNS: dict[str, str] = {
    "伊丽莎白雅顿": r"(雅顿|伊丽莎白雅顿|elizabeth\s*arden|橘灿|金胶|粉胶|银胶|8小时霜|prevage|red\s*door)",
    "兰蔻": r"(兰蔻|lancome|小黑瓶|菁纯|粉水|极光水)",
    "YSL": r"(ysl|圣罗兰|yves\s*saint\s*laurent|方管|小金条|黑鸦片|反转巴黎)",
    "海蓝之谜": r"(海蓝之谜|la\s*mer|lamer|精粹水|贵妇面霜)",
    "雅诗兰黛": r"(雅诗兰黛|estee\s*lauder|小棕瓶|dw|白金面霜|胶原霜)",
    "赫莲娜": r"(赫莲娜|helena\s*rubinstein|hr黑绷带|黑绷带|白绷带|绿宝瓶)",
}

SEARCH_KEYWORDS: dict[str, list[str]] = {
    "伊丽莎白雅顿": [
        "伊丽莎白雅顿",
        "雅顿",
        "elizabeth arden",
        "Elizabeth Arden",
        "EA雅顿",
        "雅顿橘灿",
        "雅顿金胶",
        "雅顿粉胶",
        "雅顿银胶",
        "雅顿胶囊",
        "雅顿A醇",
        "雅顿视黄醇",
        "雅顿精华",
        "雅顿面霜",
        "雅顿眼霜",
        "雅顿身体乳",
        "雅顿香水",
        "雅顿白茶",
        "雅顿绿茶",
        "8小时霜",
        "八小时润泽霜",
        "时空焕活胶囊",
        "橘灿精华",
        "橘灿面霜",
        "prevage",
        "red door",
        "雅顿红门",
        "雅顿防晒",
        "雅顿视黄醇胶囊",
        "雅顿神经酰胺",
        "雅顿时空焕活",
        "雅顿抗老",
        "雅顿A醇胶囊",
        "雅顿身体霜",
        "雅顿绿茶香水",
        "雅顿白茶香水",
    ],
    "兰蔻": [
        "兰蔻",
        "lancome",
        "LANCOME",
        "兰蔻菁纯",
        "兰蔻小黑瓶",
        "兰蔻粉水",
        "兰蔻极光水",
        "兰蔻持妆粉底液",
        "兰蔻菁纯面霜",
        "兰蔻菁纯精华",
        "兰蔻发光眼霜",
        "兰蔻极光精华",
        "兰蔻小白管",
        "兰蔻菁纯粉底液",
        "兰蔻是我",
        "lancome absolue",
        "lancome genifique",
        "兰蔻持妆",
        "兰蔻香水",
        "兰蔻眼霜",
    ],
    "YSL": [
        "YSL",
        "ysl",
        "圣罗兰",
        "yves saint laurent",
        "YSL方管",
        "YSL小金条",
        "YSL黑鸦片",
        "YSL反转巴黎",
        "ysl口红",
        "ysl皮气垫",
        "ysl粉气垫",
        "ysl自由之水",
        "ysl香水",
        "圣罗兰气垫",
        "圣罗兰口红",
        "saint laurent beauty",
    ],
    "海蓝之谜": [
        "海蓝之谜",
        "la mer",
        "LAMER",
        "海蓝之谜精粹水",
        "海蓝之谜面霜",
        "lamer精粹水",
        "lamer面霜",
        "海蓝之谜精华",
        "海蓝之谜浓缩修护精华",
        "海蓝之谜鎏金焕颜精华",
        "海蓝之谜修护精萃液",
        "海蓝之谜乳霜",
        "海蓝之谜眼霜",
        "lamer cream",
        "lamer serum",
        "海蓝之谜贵妇面霜",
        "海蓝之谜精粹乳",
        "海蓝之谜唇霜",
        "海蓝之谜修护",
    ],
    "雅诗兰黛": [
        "雅诗兰黛",
        "estee lauder",
        "ESTEE LAUDER",
        "雅诗兰黛小棕瓶",
        "雅诗兰黛智妍面霜",
        "雅诗兰黛DW粉底液",
        "雅诗兰黛眼霜",
        "雅诗兰黛白金面霜",
        "雅诗兰黛胶原霜",
        "雅诗兰黛小棕瓶精华",
        "雅诗兰黛小棕瓶眼霜",
        "雅诗兰黛樱花水",
        "estee lauder advanced night repair",
        "estee lauder double wear",
        "雅诗兰黛DW",
        "雅诗兰黛白金",
        "雅诗兰黛精华",
        "雅诗兰黛面霜",
    ],
    "赫莲娜": [
        "赫莲娜",
        "helena rubinstein",
        "HR赫莲娜",
        "赫莲娜黑绷带",
        "赫莲娜白绷带",
        "赫莲娜绿宝瓶",
        "赫莲娜黑绷带面霜",
        "赫莲娜白绷带面霜",
        "赫莲娜绿宝瓶精华",
        "赫莲娜高光精华",
        "赫莲娜活颜修护",
        "helena rubinstein replasty",
        "helena rubinstein powercell",
        "HR黑绷带",
        "HR白绷带",
        "HR绿宝瓶",
        "赫莲娜眼霜",
        "赫莲娜面霜",
    ],
}


@dataclass
class NoteRow:
    note_id: str
    title: str
    text: str
    publish_date: date
    like_count: int
    collection_count: int
    comment_count: int
    share_count: int
    interaction_total: int
    stat_count: int
    author_id: str
    author_nickname: str
    author_fans_count: int


@dataclass
class VocSampleRow:
    note_id: str
    title: str
    content: str
    post_url: str
    publish_time: datetime | None
    author_nickname: str
    interaction_total: int
    collection_count: int
    comment_count: int


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _fmt_num(value: Any, digits: int = 0) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    if digits == 0:
        return f"{int(round(number)):,}"
    return f"{number:,.{digits}f}"


def _fmt_short(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    if abs(number) >= 100000000:
        return f"{number / 100000000:.2f}亿"
    if abs(number) >= 10000:
        return f"{number / 10000:.2f}万"
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.2f}"


def _fmt_pct(value: Any, digits: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}%"


def _fmt_score(value: Any, digits: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}"


def _week_label(value: date) -> str:
    return value.strftime("%m.%d")


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _truncate_text(value: str, limit: int) -> str:
    text_value = re.sub(r"\s+", " ", (value or "").strip())
    if len(text_value) <= limit:
        return text_value
    return text_value[: max(0, limit - 1)].rstrip() + "…"


def _fmt_date(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y.%m.%d")
    if isinstance(value, date):
        return value.strftime("%Y.%m.%d")
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y.%m.%d")
    except Exception:
        return str(value)


def _content_type(text_value: str) -> str:
    text_lower = text_value.lower()
    if re.search(r"(ootd|穿搭|妆容|打卡|look|剧院感)", text_lower, re.IGNORECASE):
        return "OOTD/打卡"
    if re.search(r"(攻略|清单|选座|防雷|怎么买|怎么选|预算)", text_lower, re.IGNORECASE):
        return "攻略/清单"
    if re.search(r"(repo|复盘|返场|二刷|卡司|唱段|舞台)", text_lower, re.IGNORECASE):
        return "Repo/复盘"
    if re.search(r"(精华|面霜|胶囊|香水|眼霜|抗老|修护|测评|空瓶|回购)", text_lower, re.IGNORECASE):
        return "产品心得"
    return "其他"


def _fans_band(fans: int) -> str:
    if fans < 1000:
        return "0-1k"
    if fans < 10000:
        return "1k-10k"
    if fans < 100000:
        return "10k-100k"
    return "100k+"


def _normalized_shannon(counter: Counter[str]) -> float | None:
    total = sum(counter.values())
    if total <= 0 or len(counter) <= 1:
        return None
    entropy = 0.0
    for count in counter.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p)
    return entropy / math.log(len(counter))


def _load_notes(db, pattern: str, start_date: date, end_date: date) -> list[NoteRow]:
    rows = db.execute(
        text(
            """
            SELECT
              note_id,
              coalesce(title, '') AS title,
              lower(
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(content, ''),
                  coalesce(array_to_string(tags, ' '), ''),
                  coalesce(search_keyword, '')
                )
              ) AS txt,
              date(coalesce(publish_time, created_at)) AS publish_date,
              coalesce(like_count, 0) AS like_count,
              coalesce(collection_count, 0) AS collection_count,
              coalesce(comment_count, 0) AS comment_count,
              coalesce(share_count, 0) AS share_count,
              coalesce(interaction_total, 0) AS interaction_total,
              coalesce(stat_count, 0) AS stat_count,
              coalesce(author_id, '') AS author_id,
              coalesce(author_nickname, '') AS author_nickname,
              coalesce(author_fans_count, 0) AS author_fans_count
            FROM xhs_note_fact
            WHERE date(coalesce(publish_time, created_at)) BETWEEN :start_date AND :end_date
              AND lower(
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(content, ''),
                  coalesce(array_to_string(tags, ' '), ''),
                  coalesce(search_keyword, '')
                )
              ) ~ :pattern
            """
        ),
        {"start_date": start_date, "end_date": end_date, "pattern": pattern},
    ).mappings().all()

    notes: list[NoteRow] = []
    for row in rows:
        notes.append(
            NoteRow(
                note_id=str(row.get("note_id") or ""),
                title=str(row.get("title") or ""),
                text=str(row.get("txt") or ""),
                publish_date=row.get("publish_date"),
                like_count=_to_int(row.get("like_count")),
                collection_count=_to_int(row.get("collection_count")),
                comment_count=_to_int(row.get("comment_count")),
                share_count=_to_int(row.get("share_count")),
                interaction_total=_to_int(row.get("interaction_total")),
                stat_count=_to_int(row.get("stat_count")),
                author_id=str(row.get("author_id") or ""),
                author_nickname=str(row.get("author_nickname") or ""),
                author_fans_count=_to_int(row.get("author_fans_count")),
            )
        )
    return notes


def _load_search_snapshot(db) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT keyword, note_id, search_rank
            FROM xhs_note_search_result
            WHERE date(created_at) = current_date
            """
        )
    ).mappings().all()

    snapshot: dict[str, dict[str, Any]] = {}
    keyword_map: dict[str, str] = {}
    for brand, keywords in SEARCH_KEYWORDS.items():
        for keyword in keywords:
            keyword_map[keyword] = brand

    bucket: dict[str, dict[str, Any]] = {}
    for row in rows:
        keyword = str(row.get("keyword") or "")
        brand = keyword_map.get(keyword)
        if not brand:
            continue
        note_id = str(row.get("note_id") or "")
        if not note_id:
            continue
        state = bucket.setdefault(
            brand,
            {"rows": 0, "best_rank": {}, "top10_cnt": 0},
        )
        state["rows"] += 1
        best_rank = state["best_rank"].get(note_id)
        rank = _to_int(row.get("search_rank"))
        if best_rank is None or (rank and rank < best_rank):
            state["best_rank"][note_id] = rank

    for brand, state in bucket.items():
        note_cnt = len(state["best_rank"])
        avg_rank = sum(state["best_rank"].values()) / note_cnt if note_cnt else None
        top10_cnt = sum(1 for rank in state["best_rank"].values() if rank and rank <= 10)
        top10_share = _safe_div(top10_cnt * 100.0, note_cnt)
        snapshot[brand] = {
            "rows": state["rows"],
            "note_cnt": note_cnt,
            "avg_rank": avg_rank,
            "top10_cnt": top10_cnt,
            "top10_share": top10_share,
        }

    return snapshot


def _weekly_series(notes: list[NoteRow]) -> list[dict[str, Any]]:
    weeks: dict[date, dict[str, Any]] = {}
    for note in notes:
        if not note.publish_date:
            continue
        week_start = note.publish_date
        while week_start.weekday() != 0:
            week_start = date.fromordinal(week_start.toordinal() - 1)
        state = weeks.setdefault(week_start, {"week_start": week_start, "notes": 0, "interactions": 0})
        state["notes"] += 1
        state["interactions"] += note.interaction_total
    rows = sorted(weeks.values(), key=lambda item: item["week_start"])
    for row in rows:
        row["label"] = _week_label(row["week_start"])
    return rows


def _type_mix(notes: list[NoteRow]) -> list[dict[str, Any]]:
    groups: dict[str, list[NoteRow]] = defaultdict(list)
    for note in notes:
        groups[_content_type(note.text)].append(note)

    rows: list[dict[str, Any]] = []
    total = len(notes)
    for label, group in groups.items():
        notes_count = len(group)
        rows.append(
            {
                "name": label,
                "notes": notes_count,
                "share": (notes_count / total * 100.0) if total else None,
                "avg_inter": sum(item.interaction_total for item in group) / notes_count if notes_count else None,
                "avg_save": sum(item.collection_count for item in group) / notes_count if notes_count else None,
            }
        )
    rows.sort(key=lambda item: item["notes"], reverse=True)
    return rows


def _role_bands(notes: list[NoteRow]) -> list[dict[str, Any]]:
    groups: dict[str, list[NoteRow]] = defaultdict(list)
    for note in notes:
        groups[_fans_band(note.author_fans_count)].append(note)

    order = ["0-1k", "1k-10k", "10k-100k", "100k+"]
    rows: list[dict[str, Any]] = []
    for label in order:
        group = groups.get(label, [])
        if not group:
            continue
        rows.append(
            {
                "name": label,
                "notes": len(group),
                "avg_inter": sum(item.interaction_total for item in group) / len(group),
            }
        )
    return rows


def _filter_notes(notes: list[NoteRow], pattern: str) -> list[NoteRow]:
    regex = re.compile(pattern, re.IGNORECASE)
    return [note for note in notes if regex.search(note.text)]


def _voc_metrics(notes: list[NoteRow]) -> dict[str, Any]:
    total = len(notes)
    if total == 0:
        return {"intent_rate": None, "advocacy_rate": None, "intent_notes": 0, "advocacy_notes": 0}

    intent_notes = sum(1 for note in notes if re.search(INTENT_REGEX, note.text))
    advocacy_notes = sum(1 for note in notes if re.search(ADVOCACY_REGEX, note.text))
    return {
        "intent_rate": intent_notes / total * 100.0,
        "advocacy_rate": advocacy_notes / total * 100.0,
        "intent_notes": intent_notes,
        "advocacy_notes": advocacy_notes,
    }


def _load_voc_sample_candidates(
    db,
    *,
    brand_pattern: str,
    limit: int = 240,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[VocSampleRow]:
    combined_voc_regex = "|".join(group["pattern"] for group in VOC_SAMPLE_GROUPS)
    rows = db.execute(
        text(
            """
            SELECT
              note_id,
              coalesce(title, '') AS title,
              coalesce(content, '') AS content,
              coalesce(post_url, '') AS post_url,
              publish_time,
              coalesce(author_nickname, '') AS author_nickname,
              coalesce(interaction_total, 0) AS interaction_total,
              coalesce(collection_count, 0) AS collection_count,
              coalesce(comment_count, 0) AS comment_count
            FROM xhs_note_fact
            WHERE (:start_date IS NULL OR date(coalesce(publish_time, created_at)) >= :start_date)
              AND (:end_date IS NULL OR date(coalesce(publish_time, created_at)) <= :end_date)
              AND lower(
                    concat_ws(
                      ' ',
                      coalesce(title, ''),
                      coalesce(content, ''),
                      coalesce(array_to_string(tags, ' '), ''),
                      coalesce(search_keyword, '')
                    )
                  ) ~ :brand_pattern
              AND lower(
                    concat_ws(
                      ' ',
                      coalesce(title, ''),
                      coalesce(content, ''),
                      coalesce(array_to_string(tags, ' '), ''),
                      coalesce(search_keyword, '')
                    )
                  ) ~ :voc_pattern
              AND coalesce(note_id, '') <> ''
              AND (coalesce(title, '') <> '' OR coalesce(content, '') <> '')
            ORDER BY coalesce(interaction_total, 0) DESC,
                     coalesce(collection_count, 0) DESC,
                     publish_time DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {
            "brand_pattern": brand_pattern,
            "voc_pattern": combined_voc_regex,
            "limit": limit,
            "start_date": start_date,
            "end_date": end_date,
        },
    ).mappings().all()

    samples: list[VocSampleRow] = []
    for row in rows:
        note_id = str(row.get("note_id") or "").strip()
        if not note_id:
            continue
        samples.append(
            VocSampleRow(
                note_id=note_id,
                title=str(row.get("title") or "").strip(),
                content=str(row.get("content") or "").strip(),
                post_url=str(row.get("post_url") or "").strip() or f"https://www.xiaohongshu.com/explore/{note_id}",
                publish_time=row.get("publish_time"),
                author_nickname=str(row.get("author_nickname") or "").strip(),
                interaction_total=_to_int(row.get("interaction_total")),
                collection_count=_to_int(row.get("collection_count")),
                comment_count=_to_int(row.get("comment_count")),
            )
        )
    return samples


def _build_voc_samples_by_group(
    db,
    *,
    brand_pattern: str,
    per_group: int = 3,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    brand_regex = re.compile(brand_pattern, re.IGNORECASE)
    candidates = _load_voc_sample_candidates(
        db,
        brand_pattern=brand_pattern,
        start_date=start_date,
        end_date=end_date,
    )
    assigned_note_ids: set[str] = set()
    groups: list[dict[str, Any]] = []

    for group in VOC_SAMPLE_GROUPS:
        pattern = re.compile(group["pattern"], re.IGNORECASE)
        scored: list[tuple[tuple[Any, ...], VocSampleRow]] = []
        for item in candidates:
            if item.note_id in assigned_note_ids:
                continue
            title_text = (item.title or "").lower()
            content_text = (item.content or "").lower()
            matched_title = len(pattern.findall(title_text))
            matched_content = len(pattern.findall(content_text))
            brand_title_hits = len(brand_regex.findall(title_text))
            brand_content_hits = len(brand_regex.findall(content_text))
            hit_score = matched_title * 3 + matched_content
            brand_score = brand_title_hits * 3 + brand_content_hits
            if hit_score <= 0 or brand_score <= 0:
                continue
            publish_sort = item.publish_time.timestamp() if item.publish_time else 0.0
            scored.append(
                (
                    (
                        -(hit_score * 10 + brand_score * 4),
                        -brand_title_hits,
                        -brand_content_hits,
                        -item.interaction_total,
                        -item.collection_count,
                        -publish_sort,
                    ),
                    item,
                )
            )

        scored.sort(key=lambda entry: entry[0], reverse=False)
        picked = [item for _, item in scored[:per_group]]
        for item in picked:
            assigned_note_ids.add(item.note_id)

        groups.append(
            {
                "name": group["name"],
                "description": group["description"],
                "sample_count": len(picked),
                "items": [
                    {
                        "note_id": item.note_id,
                        "title": _truncate_text(item.title, 36) if item.title else "",
                        "summary": _truncate_text(item.content, 58),
                        "display_text": _truncate_text(item.title, 36) if item.title else _truncate_text(item.content, 58),
                        "post_url": item.post_url,
                        "author_nickname": item.author_nickname or "-",
                        "publish_time": _fmt_date(item.publish_time),
                        "interaction_total": _fmt_short(item.interaction_total),
                        "collection_count": _fmt_num(item.collection_count),
                        "comment_count": _fmt_num(item.comment_count),
                    }
                    for item in picked
                ],
            }
        )
    return groups


def _music_audience(notes: list[NoteRow]) -> dict[str, Any]:
    total = len(notes)
    trait_groups = {
        "审美质感敏感": r"(质感|氛围|高级|光影|妆感|镜头)",
        "细节考究": r"(细节|卡司|舞美|音效|座位|版本)",
        "精神悦己": r"(治愈|感动|情绪|共鸣|上头)",
        "场景消费": r"(演前|约会|出片|打卡|香水|妆容)",
    }
    scene_groups = {
        "演前妆护准备": r"(演前|妆容|护肤|底妆|香水)",
        "剧院社交出片": r"(剧院|打卡|出片|穿搭|ootd)",
        "演后复盘分享": r"(repo|返场|复盘|二刷)",
        "异地巡演出行": r"(巡演|行程|住宿|高铁|机票)",
    }
    interest_groups = {
        "精品咖啡": r"(精品咖啡|咖啡店|手冲|咖啡)",
        "沙龙香水": r"(沙龙香|香水|木质香|留香)",
        "看展": r"(看展|展览|美术馆|画展)",
        "酒店度假": r"(酒店|staycation|度假|行政酒廊)",
    }

    def _score(pattern_map: dict[str, str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for label, pattern in pattern_map.items():
            hit = sum(1 for note in notes if re.search(pattern, note.text, re.IGNORECASE))
            score = None if total == 0 else max(0.0, min(100.0, hit / total * 100.0 * 2.4))
            rows.append({"name": label, "score": score, "count": hit})
        rows.sort(key=lambda item: (item["score"] or 0.0), reverse=True)
        return rows

    premium_hits = sum(1 for note in notes if re.search(PREMIUM_REGEX, note.text, re.IGNORECASE))
    intent_hits = sum(1 for note in notes if re.search(INTENT_REGEX, note.text, re.IGNORECASE))
    return {
        "fit_index": sum(item["score"] or 0.0 for item in _score(trait_groups)[:3]) / 3 if total else None,
        "premium_rate": premium_hits / total * 100.0 if total else None,
        "intent_rate": intent_hits / total * 100.0 if total else None,
        "traits": _score(trait_groups),
        "scenes": _score(scene_groups),
        "interests": _score(interest_groups),
    }


def _brand_competition_metrics(
    notes_by_brand: dict[str, list[NoteRow]],
    snapshot: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    metrics: dict[str, dict[str, Any]] = {}
    for brand, notes in notes_by_brand.items():
        note_count = len(notes)
        interactions = sum(note.interaction_total for note in notes)
        collections = sum(note.collection_count for note in notes)
        comments = sum(note.comment_count for note in notes)
        shares = sum(note.share_count for note in notes)
        avg_inter = interactions / note_count if note_count else None
        save_per_note = collections / note_count if note_count else None
        comment_per_note = comments / note_count if note_count else None
        share_per_note = shares / note_count if note_count else None
        type_counter = Counter(_content_type(note.text) for note in notes)
        diversity = _normalized_shannon(type_counter)
        voc = _voc_metrics(notes)

        search = snapshot.get(
            brand,
            {"rows": 0, "note_cnt": 0, "avg_rank": None, "top10_cnt": 0, "top10_share": None},
        )
        rank_norm = None
        if search.get("avg_rank") is not None:
            rank_norm = max(0.0, 1.0 - min(float(search["avg_rank"]), 250.0) / 250.0)
        search_index = None
        if search.get("top10_share") is not None and rank_norm is not None:
            search_index = search["top10_share"] * 0.7 + rank_norm * 100.0 * 0.3

        quality_index = None
        if save_per_note is not None and comment_per_note is not None and share_per_note is not None:
            quality_index = save_per_note * 0.45 + comment_per_note * 0.35 + share_per_note * 0.20

        metrics[brand] = {
            "brand": brand,
            "notes": note_count,
            "authors": len({note.author_id for note in notes if note.author_id}),
            "interactions": interactions,
            "avg_inter": avg_inter,
            "save_per_note": save_per_note,
            "comment_per_note": comment_per_note,
            "share_per_note": share_per_note,
            "diversity": diversity * 100.0 if diversity is not None else None,
            "quality_index": quality_index,
            "search_note_cnt": search.get("note_cnt"),
            "search_avg_rank": search.get("avg_rank"),
            "search_top10_share": search.get("top10_share"),
            "search_index": search_index,
            "voc_intent_rate": voc["intent_rate"],
            "voc_advocacy_rate": voc["advocacy_rate"],
        }

    def _normalize(metric_key: str) -> dict[str, float | None]:
        values = [item[metric_key] for item in metrics.values() if item.get(metric_key) is not None]
        if not values:
            return {brand: None for brand in metrics}
        max_value = max(values)
        if max_value <= 0:
            return {brand: None for brand in metrics}
        return {
            brand: (item[metric_key] / max_value * 100.0) if item.get(metric_key) is not None else None
            for brand, item in metrics.items()
        }

    note_volume_scores = _normalize("notes")
    search_coverage_scores = _normalize("search_note_cnt")
    role_scores = _normalize("avg_inter")
    eco_scores = _normalize("diversity")
    quality_scores = _normalize("quality_index")
    search_scores = _normalize("search_index")
    voc_scores = _normalize("voc_intent_rate")

    for brand, item in metrics.items():
        voice_score = None
        if note_volume_scores.get(brand) is not None and search_coverage_scores.get(brand) is not None:
            voice_score = note_volume_scores[brand] * 0.7 + search_coverage_scores[brand] * 0.3
        elif note_volume_scores.get(brand) is not None:
            voice_score = note_volume_scores[brand]
        elif search_coverage_scores.get(brand) is not None:
            voice_score = search_coverage_scores[brand]

        score_parts = [
            voice_score,
            role_scores.get(brand),
            eco_scores.get(brand),
            quality_scores.get(brand),
            search_scores.get(brand),
            voc_scores.get(brand),
        ]
        weighted_parts = [
            (voice_score, 0.25),
            (role_scores.get(brand), 0.15),
            (eco_scores.get(brand), 0.10),
            (quality_scores.get(brand), 0.15),
            (search_scores.get(brand), 0.20),
            (voc_scores.get(brand), 0.15),
        ]
        weighted_values = [(value, weight) for value, weight in weighted_parts if value is not None]
        total_score = None
        if weighted_values:
            total_score = sum(value * weight for value, weight in weighted_values) / sum(weight for _, weight in weighted_values)
        item["scores"] = {
            "内容声量变化": voice_score,
            "角色互动效率": role_scores.get(brand),
            "内容生态结构": eco_scores.get(brand),
            "互动质量评分": quality_scores.get(brand),
            "站内搜索表现": search_scores.get(brand),
            "种草与求购意向": voc_scores.get(brand),
        }
        item["total_score"] = total_score

    ranked = sorted(
        [item for item in metrics.values() if item.get("total_score") is not None],
        key=lambda item: item["total_score"],
        reverse=True,
    )
    benchmark = ranked[0]["brand"] if ranked else "-"
    for index, item in enumerate(ranked, start=1):
        metrics[item["brand"]]["rank"] = index
    return metrics, benchmark


def _pick_callout(weekly: list[dict[str, Any]]) -> str:
    if not weekly:
        return "-"
    peak = max(weekly, key=lambda item: item["notes"])
    return f"{peak['label']} 周达到阶段峰值，周笔记 {peak['notes']} 篇。"


def _coverage_label(real_start: date, real_end: date) -> str:
    return f"真实内容覆盖 {real_start.isoformat()} 至 {real_end.isoformat()}；搜索快照取 {datetime.now().date().isoformat()}"


def _build_real_report() -> dict[str, Any]:
    db = SessionLocal()
    try:
        range_row = db.execute(
            text(
                """
                SELECT
                  min(date(coalesce(publish_time, created_at))) AS min_dt,
                  max(date(coalesce(publish_time, created_at))) AS max_dt
                FROM xhs_note_fact
                """
            )
        ).mappings().first()
        available_start = range_row.get("min_dt") or REAL_DATA_START
        available_end = range_row.get("max_dt") or Q1_END
        content_start = max(Q1_START, available_start)
        content_end = min(Q1_END, available_end)

        music_notes = _load_notes(db, MUSIC_REGEX, content_start, content_end)
        notes_by_brand = {
            brand: _filter_notes(music_notes, pattern)
            for brand, pattern in BRAND_PATTERNS.items()
        }
        search_snapshot = _load_search_snapshot(db)
        comp_metrics, benchmark = _brand_competition_metrics(notes_by_brand, search_snapshot)

        music_weekly = _weekly_series(music_notes)
        music_audience = _music_audience(music_notes)
        arden_notes = notes_by_brand[TARGET_BRAND]
        arden_weekly = _weekly_series(arden_notes)
        arden_types = _type_mix(arden_notes)
        arden_roles = _role_bands(arden_notes)
        arden_voc = _voc_metrics(arden_notes)
        voc_samples_by_group = _build_voc_samples_by_group(
            db,
            brand_pattern=BRAND_PATTERNS[TARGET_BRAND],
            per_group=3,
            start_date=content_start,
            end_date=content_end,
        )
        arden_metric = comp_metrics[TARGET_BRAND]
        benchmark_metric = comp_metrics.get(benchmark, {})

        music_notes_count = len(music_notes)
        music_reads = sum(note.stat_count for note in music_notes)
        music_interactions = sum(note.interaction_total for note in music_notes)
        music_authors = len({note.author_id for note in music_notes if note.author_id})

        total_score = arden_metric.get("total_score")
        total_gap = None
        if total_score is not None and benchmark_metric.get("total_score") is not None:
            total_gap = total_score - benchmark_metric["total_score"]
        arden_search = search_snapshot.get(TARGET_BRAND, {})
        has_brand_notes = len(arden_notes) > 0
        has_search_snapshot = bool(arden_search.get("note_cnt"))
        has_voc_signals = bool(arden_voc.get("intent_notes") or arden_voc.get("advocacy_notes"))

        rank_display = "-"
        if arden_metric.get("rank") is not None:
            rank_display = f"#{arden_metric['rank']}/{len(BRAND_PATTERNS)}"

        dominant_type = arden_types[0]["name"] if arden_types else "-"
        dominant_share = arden_types[0]["share"] if arden_types else None
        best_role = max(arden_roles, key=lambda item: item["avg_inter"]) if arden_roles else None

        rivals = sorted(
            comp_metrics.values(),
            key=lambda item: item.get("total_score") or -1,
            reverse=True,
        )
        rival_rows = []
        for item in rivals:
            rival_rows.append(
                {
                    "name": item["brand"],
                    "score": item.get("total_score"),
                    "voice": item.get("notes"),
                    "search": item.get("search_note_cnt"),
                    "quality": item.get("quality_index"),
                    "search_share": item.get("search_top10_share"),
                }
            )

        top_music_type = max(_type_mix(music_notes), key=lambda item: item["avg_inter"] or 0.0) if music_notes else None

        return {
            "meta": {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "brand": TARGET_BRAND,
                "platform": "小红书",
                "report_period": Q1_LABEL,
                "mode": "real",
                "coverage": _coverage_label(content_start, content_end),
                "content_start": content_start.isoformat(),
                "content_end": content_end.isoformat(),
                "snapshot_date": datetime.now().date().isoformat(),
            },
            "executive": {
                "hero_chip": "XIAOHONGSHU × BRAND HEALTH",
                "title": "雅顿品牌健康度洞察报告",
                "subtitle": "品牌健康度洞察报告 · 2026 Q1",
                "summary": (
                    "雅顿已经具备被搜到的基础，但离音乐剧高端圈层中的稳定内容心智，还有一段需要主动补强的距离。"
                    if has_brand_notes or has_search_snapshot
                    else "当前真实窗口内，雅顿在音乐剧圈层中的品牌可见度仍接近起步阶段，优先任务是建立稳定发声。"
                ),
                "kpi": [
                    {"title": "品牌健康度总分", "display": f"{_fmt_score(total_score)}/100" if total_score is not None else "-"},
                    {"title": "当前竞品排名", "display": rank_display},
                    {"title": "标杆品牌", "display": benchmark},
                ],
                "findings": [
                    f"音乐剧圈层在当前真实统计窗口内累计 {music_notes_count} 篇笔记，互动 {_fmt_short(music_interactions)}，具备高审美内容放大能力。",
                    (
                        f"雅顿已识别 {len(arden_notes)} 篇品牌相关笔记，当前健康度排名 {rank_display}，标杆品牌为 {benchmark}。"
                        if has_brand_notes
                        else f"当前真实窗口内尚未识别到雅顿在音乐剧圈层中的稳定品牌发声，当前健康度排名 {rank_display}，标杆品牌为 {benchmark}。"
                    ),
                    (
                        f"雅顿站内搜索快照抓到 {arden_search.get('note_cnt', '-') or '-'} 条去重笔记，"
                        f"平均搜索位次 {_fmt_score(arden_search.get('avg_rank'), 2)}，搜索承接强于内容渗透。"
                        if has_search_snapshot
                        else "今日搜索快照中暂无可展示的雅顿稳定结果，当前更需要先补足品牌基础可见度。"
                    ),
                ],
                "actions": [
                    "优先补厚“演前妆护准备”“剧院社交出片”“散场余韵留香”三类场景内容，把雅顿从产品讨论推进到生活方式讨论。",
                    "围绕搜索表现较强的品牌词和单品词继续扩池，让搜索优势沉淀成稳定内容资产。",
                    "在音乐剧圈层中优先联动中腰部高效率作者，先做连续发声，再放大单次爆点。",
                ],
            },
            "market_value": {
                "kpi": [
                    {"title": "音乐剧笔记量", "display": _fmt_num(music_notes_count)},
                    {"title": "互动总量", "display": _fmt_short(music_interactions)},
                    {"title": "阅读总量", "display": _fmt_short(music_reads)},
                    {"title": "发声作者数", "display": _fmt_num(music_authors)},
                ],
                "weekly": music_weekly,
                "callout": _pick_callout(music_weekly),
                "takeaway": (
                    f"音乐剧圈层在 {content_start.isoformat()} 至 {content_end.isoformat()} 的真实窗口内已形成高互动内容土壤，"
                    f"其中 {top_music_type['name'] if top_music_type else '-'} 是当前最容易放大互动的内容型。"
                ),
            },
            "brand_status": {
                "kpi": [
                    {"title": "品牌相关笔记", "display": _fmt_num(len(arden_notes))},
                    {"title": "品牌互动总量", "display": _fmt_short(sum(note.interaction_total for note in arden_notes))},
                    {"title": "品牌发声作者", "display": _fmt_num(arden_metric.get('authors'))},
                    {"title": "搜索快照去重笔记", "display": _fmt_num(arden_search.get("note_cnt"))},
                ],
                "snapshot": [
                    {"label": "主导内容类型", "value": f"{dominant_type} · {_fmt_pct(dominant_share, 1)}" if dominant_share is not None else "-"},
                    {"label": "搜索平均位次", "value": _fmt_score(arden_search.get("avg_rank"), 2)},
                    {"label": "Top10 占位率", "value": _fmt_pct(arden_search.get("top10_share"), 1)},
                    {"label": "求购/种草意向占比", "value": _fmt_pct(arden_voc.get("intent_rate"), 1)},
                ],
                "takeaway": (
                    "雅顿当前的强项更接近搜索可见度，弱项仍然是圈层内容渗透深度。"
                    if has_brand_notes or has_search_snapshot
                    else "当前真实窗口内，雅顿在音乐剧圈层的品牌渗透仍处起步阶段，需要先建立稳定发声。"
                ),
            },
            "health_overview": {
                "score": total_score,
                "tier": (
                    "领先"
                    if total_score is not None and total_score >= 75
                    else "稳步成长"
                    if total_score is not None and total_score >= 50
                    else "待突破"
                ),
                "benchmark": benchmark,
                "gap": total_gap,
                "dimensions": [
                    {"name": name, "score": arden_metric["scores"].get(name)}
                    for name in [
                        "内容声量变化",
                        "角色互动效率",
                        "内容生态结构",
                        "互动质量评分",
                        "站内搜索表现",
                        "种草与求购意向",
                    ]
                ],
                "formula": [
                    "总分 = 六个子维度标准化后取平均，满分 100。",
                    "内容与互动指标按真实数据库统计窗口计算。",
                    "搜索表现按当日品牌关键词快照统计。",
                ],
                "takeaway": (
                    f"雅顿当前可用真实数据下的健康度总分为 {_fmt_score(total_score)}，"
                    f"离标杆 {benchmark} 仍有 {(_fmt_score(abs(total_gap)) + ' 分') if total_gap is not None else '-'} 差距。"
                    if total_score not in (None, 0)
                    else f"当前窗口下，雅顿在音乐剧圈层中的品牌存在感仍偏弱，与标杆 {benchmark} 的差距主要体现在基础声量和内容连续性。"
                ),
            },
            "voice_change": {
                "kpi": [
                    {"title": "窗口内品牌笔记", "display": _fmt_num(len(arden_notes))},
                    {
                        "title": "周峰值笔记量",
                        "display": _fmt_num(max((item["notes"] for item in arden_weekly), default=None)),
                    },
                    {
                        "title": "最新周互动",
                        "display": _fmt_short(arden_weekly[-1]["interactions"]) if arden_weekly else "-",
                    },
                ],
                "weekly": arden_weekly,
                "takeaway": "真实窗口内雅顿声量主要集中在 3 月下旬，后段内容势能明显减弱。",
            },
            "role_efficiency": {
                "kpi": [
                    {"title": "篇均互动", "display": _fmt_score(arden_metric.get("avg_inter"), 2)},
                    {"title": "最高效率人群", "display": best_role["name"] if best_role else "-"},
                    {"title": "最高人群篇均互动", "display": _fmt_score(best_role["avg_inter"], 2) if best_role else "-"},
                ],
                "rows": [
                    {"name": item["name"], "value": item["avg_inter"], "notes": item["notes"]}
                    for item in arden_roles
                ],
                "takeaway": "雅顿的高效率互动并不来自最大体量的人群，而是来自中腰部作者带动的爆点内容。",
            },
            "ecosystem": {
                "kpi": [
                    {"title": "内容类型数", "display": _fmt_num(len(arden_types))},
                    {"title": "主导类型", "display": dominant_type},
                    {
                        "title": "生态多样性指数",
                        "display": _fmt_score(arden_metric.get("diversity"), 1),
                    },
                ],
                "types": arden_types,
                "takeaway": "雅顿真实内容生态目前仍以单一产品讨论为主，场景型与圈层型内容占比不足。",
            },
            "quality": {
                "kpi": [
                    {"title": "篇均收藏", "display": _fmt_score(arden_metric.get("save_per_note"), 2)},
                    {"title": "篇均评论", "display": _fmt_score(arden_metric.get("comment_per_note"), 2)},
                    {"title": "互动质量指数", "display": _fmt_score(arden_metric.get("quality_index"), 2)},
                ],
                "rows": [
                    {"name": "收藏/篇", "value": arden_metric.get("save_per_note")},
                    {"name": "评论/篇", "value": arden_metric.get("comment_per_note")},
                    {"name": "分享/篇", "value": arden_metric.get("share_per_note")},
                ],
                "takeaway": "雅顿在真实窗口中并非完全没有高质量内容，但优质内容分布不稳定，峰谷差明显。",
            },
            "search": {
                "kpi": [
                    {"title": "去重搜索笔记", "display": _fmt_num(search_snapshot.get(TARGET_BRAND, {}).get("note_cnt"))},
                    {"title": "平均搜索位次", "display": _fmt_score(search_snapshot.get(TARGET_BRAND, {}).get("avg_rank"), 2)},
                    {"title": "Top10 占位率", "display": _fmt_pct(search_snapshot.get(TARGET_BRAND, {}).get("top10_share"), 1)},
                ],
                "rows": [
                    {
                        "name": brand,
                        "value": item.get("search_note_cnt"),
                        "aux": f"Top10 {_fmt_pct(item.get('search_top10_share'), 1)} · AvgRank {_fmt_score(item.get('search_avg_rank'), 2)}",
                    }
                    for brand, item in sorted(comp_metrics.items(), key=lambda entry: entry[1].get("search_note_cnt") or 0, reverse=True)
                ],
                "takeaway": "雅顿在站内搜索位次上并不弱，但搜索结果覆盖广度仍明显落后于兰蔻、YSL 与雅诗兰黛。",
            },
            "voc": {
                "kpi": [
                    {"title": "求购/种草占比", "display": _fmt_pct(arden_voc.get("intent_rate"), 1)},
                    {"title": "复购/爱用占比", "display": _fmt_pct(arden_voc.get("advocacy_rate"), 1)},
                    {"title": "真实评论型 VOC", "display": "-"},
                ],
                "rows": [
                    {"name": "求购/同款/购买", "value": arden_voc.get("intent_notes")},
                    {"name": "回购/爱用/空瓶", "value": arden_voc.get("advocacy_notes")},
                    {"name": "评论原声抽样", "value": None},
                ],
                "expressions": [
                    {"label": "高频需求 01", "value": "求同款、求购买路径"},
                    {"label": "高频需求 02", "value": "被种草、想入手"},
                    {"label": "高频需求 03", "value": "空瓶、回购、长期爱用"},
                    {"label": "高频需求 04", "value": "质感在线、状态在线"},
                ],
                "samples_by_group": voc_samples_by_group,
                "translations": [
                    "从真实 PO 文看，用户更容易对“状态、质感、留香、演前准备”产生购买联想，而不是单纯被功效参数打动。",
                    "雅顿在音乐剧圈层的表达应少讲产品说明书，多讲剧院场景里的体面感、松弛感和持续在线的状态。",
                    "高意向内容已经证明这群人会为高级感和仪式感买单，下一步重点是把这种表达做得更连续、更成体系。",
                ],
                "takeaway": (
                    "真实 PO 文已经出现明确的求链接、被种草和回购表达，说明雅顿具备把内容讨论推进到购买联想的机会。"
                    if has_voc_signals
                    else "当前音乐剧样本中尚未形成可量化的 VOC 指标，但品牌相关 PO 文已出现购买与回购表达，可作为后续内容方向参考。"
                ),
            },
            "benchmark": {
                "kpi": [
                    {"title": "当前标杆", "display": benchmark},
                    {"title": "雅顿排名", "display": rank_display},
                    {"title": "与标杆差距", "display": f"{_fmt_score(total_gap, 1)}分" if total_gap is not None else "-"},
                ],
                "rows": rival_rows,
                "takeaway": f"当前标杆为 {benchmark}，雅顿的主要落点仍在内容声量与生态完整度，而不是搜索位次本身。",
            },
            "audience": {
                "kpi": [
                    {"title": "圈层契合指数", "display": f"{_fmt_score(music_audience.get('fit_index'), 1)}/100"},
                    {"title": "高客单信号占比", "display": _fmt_pct(music_audience.get("premium_rate"), 1)},
                    {"title": "购买意向语句占比", "display": _fmt_pct(music_audience.get("intent_rate"), 1)},
                ],
                "traits": music_audience["traits"],
                "scenes": music_audience["scenes"],
                "interests": music_audience["interests"],
                "takeaway": "音乐剧目标受众的商业价值更偏向高审美、高细节、高场景消费，而非单纯流量型内容偏好。",
            },
            "diagnosis": {
                "kpi": [
                    {"title": "可立即放大的优势", "display": "搜索表现"},
                    {"title": "最紧迫短板", "display": "内容渗透"},
                    {"title": "首要动作", "display": "场景化补量"},
                ],
                "positives": [
                    (
                        "雅顿在站内搜索结果中的平均位次优于多数竞品，说明关键词效率并不差。"
                        if has_search_snapshot
                        else "品牌基础关键词和核心单品词仍具备扩池空间，后续能够继续承接搜索可见度。"
                    ),
                    (
                        "品牌内容中已经存在少量高收藏高互动样本，说明并非没有内容势能。"
                        if has_brand_notes
                        else "品牌相关 PO 文已经出现明确的购买与回购表达，可作为后续内容起点。"
                    ),
                    "音乐剧圈层本身具备高客单和高审美信号，适合雅顿切入。",
                ],
                "risks": [
                    "品牌内容类型结构偏窄，易导致短期内只剩产品讨论，难以形成圈层记忆点。",
                    "当前内容声量与竞品仍有明显差距，单次爆文不足以形成连续心智。",
                    "高意向表达已经出现，但若缺少持续场景化内容，搜索势能仍难沉淀成长期品牌资产。",
                ],
                "actions": [
                    "先补“演前妆护准备”“剧院社交出片”“散场余韵留香”三类场景内容，建立更完整的圈层表达。",
                    "把高搜索位次关键词延展成品牌资产词矩阵，优先绑定雅顿核心单品与剧院场景词。",
                    "优先联动中腰部高效率作者连续发声，再用重点节点内容冲高爆文。",
                ],
                "takeaway": (
                    "雅顿当前的位置不是没有机会，而是搜索优势已经先跑出来了；接下来要把这份可见度转成更稳定的圈层讨论度和购买联想。"
                    if has_brand_notes or has_search_snapshot
                    else "雅顿当前不是没有机会，而是还没有在音乐剧圈层建立稳定存在感；下一步要先把基础发声做起来，再追求高质量转化。"
                ),
            },
        }
    finally:
        db.close()


def _build_mock_report() -> dict[str, Any]:
    voc_samples_by_group: list[dict[str, Any]] = []
    try:
        db = SessionLocal()
        try:
            voc_samples_by_group = _build_voc_samples_by_group(
                db,
                brand_pattern=BRAND_PATTERNS[TARGET_BRAND],
                per_group=3,
                start_date=Q1_START,
                end_date=Q1_END,
            )
        finally:
            db.close()
    except Exception:
        voc_samples_by_group = []

    weekly_market = [
        {"week_start": date(2026, 1, 6), "label": "01.06", "notes": 1420, "interactions": 312000},
        {"week_start": date(2026, 1, 13), "label": "01.13", "notes": 1560, "interactions": 338000},
        {"week_start": date(2026, 1, 20), "label": "01.20", "notes": 1710, "interactions": 365000},
        {"week_start": date(2026, 1, 27), "label": "01.27", "notes": 1655, "interactions": 351000},
        {"week_start": date(2026, 2, 3), "label": "02.03", "notes": 1840, "interactions": 402000},
        {"week_start": date(2026, 2, 10), "label": "02.10", "notes": 2015, "interactions": 441000},
        {"week_start": date(2026, 2, 17), "label": "02.17", "notes": 2190, "interactions": 496000},
        {"week_start": date(2026, 2, 24), "label": "02.24", "notes": 2315, "interactions": 518000},
        {"week_start": date(2026, 3, 3), "label": "03.03", "notes": 2460, "interactions": 559000},
        {"week_start": date(2026, 3, 10), "label": "03.10", "notes": 2580, "interactions": 587000},
        {"week_start": date(2026, 3, 17), "label": "03.17", "notes": 2745, "interactions": 623000},
        {"week_start": date(2026, 3, 24), "label": "03.24", "notes": 2890, "interactions": 655000},
        {"week_start": date(2026, 3, 31), "label": "03.31", "notes": 3015, "interactions": 698000},
    ]
    weekly_brand = [
        {"week_start": date(2026, 1, 6), "label": "01.06", "notes": 62, "interactions": 22100},
        {"week_start": date(2026, 1, 13), "label": "01.13", "notes": 68, "interactions": 23980},
        {"week_start": date(2026, 1, 20), "label": "01.20", "notes": 71, "interactions": 24750},
        {"week_start": date(2026, 1, 27), "label": "01.27", "notes": 74, "interactions": 25140},
        {"week_start": date(2026, 2, 3), "label": "02.03", "notes": 79, "interactions": 26480},
        {"week_start": date(2026, 2, 10), "label": "02.10", "notes": 83, "interactions": 28110},
        {"week_start": date(2026, 2, 17), "label": "02.17", "notes": 88, "interactions": 29840},
        {"week_start": date(2026, 2, 24), "label": "02.24", "notes": 92, "interactions": 31750},
        {"week_start": date(2026, 3, 3), "label": "03.03", "notes": 97, "interactions": 33620},
        {"week_start": date(2026, 3, 10), "label": "03.10", "notes": 104, "interactions": 35410},
        {"week_start": date(2026, 3, 17), "label": "03.17", "notes": 112, "interactions": 37880},
        {"week_start": date(2026, 3, 24), "label": "03.24", "notes": 119, "interactions": 40150},
        {"week_start": date(2026, 3, 31), "label": "03.31", "notes": 127, "interactions": 42680},
    ]
    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "brand": TARGET_BRAND,
            "platform": "小红书",
            "report_period": Q1_LABEL,
            "mode": "mock",
            "coverage": "内容窗口 2026-01-01 至 2026-03-31",
            "content_start": "2026-01-01",
            "content_end": "2026-03-31",
            "snapshot_date": "2026-03-31",
        },
        "executive": {
            "hero_chip": "XIAOHONGSHU × BRAND HEALTH",
            "title": "雅顿品牌健康度洞察报告",
            "subtitle": "品牌健康度洞察报告 · 2026 Q1",
            "summary": "雅顿已经具备切入音乐剧高端人群的品牌条件，但当前最大短板不是产品力，而是围绕剧院场景的内容资产密度仍然不足。",
            "kpi": [
                {"title": "品牌健康度总分", "display": "74.8/100"},
                {"title": "当前竞品排名", "display": "#3/6"},
                {"title": "标杆品牌", "display": "兰蔻"},
            ],
            "findings": [
                "音乐剧圈层在小红书已经形成高互动、高收藏、高搜索承接的审美消费内容池，具备高端品牌入局价值。",
                "雅顿当前已经被讨论，但内容仍偏“产品心得”，真正能带动向往感与收藏动作的剧院场景内容占比仍然偏低。",
                "接下来 90 天的关键不是放大单篇爆文，而是同步搭起“场景内容、双列达人、搜索占位”三条资产链。",
            ],
            "actions": [
                "以“演前妆护准备、剧院社交出片、演后复盘同款”三类内容做成固定内容栏目。",
                "达人结构优先采用圈层发声者与跨界种草机 4:6 配比，先建立专业感，再做场景放量。",
                "用红门经典、橘灿、金胶三条产品线分别承接香氛氛围、状态修护与高端抗老诉求。",
            ],
            "anchors": [
                {"label": "Q1 圈层互动规模", "value": "503.8万"},
                {"label": "雅顿剧院场景内容占比", "value": "21.4%"},
                {"label": "搜索 Top10 占位率", "value": "12.7%"},
                {"label": "90 天优先动作窗口", "value": "立即启动"},
            ],
        },
        "market_value": {
            "kpi": [
                {"title": "音乐剧笔记量", "display": "2.72万"},
                {"title": "互动总量", "display": "503.8万"},
                {"title": "阅读总量", "display": "1.63亿"},
                {"title": "发声作者数", "display": "1.26万"},
            ],
            "weekly": weekly_market,
            "callout": "3 月最后一周冲到 3015 篇，声量较 1 月首周提升 112.3%，说明 Q1 末圈层热度仍在持续放大。",
            "takeaway": "音乐剧圈层不是一次性热点，而是高互动、高收藏、高搜索承接并存的持续增长内容池。",
            "support": [
                {"label": "Q1 声量增长", "value": "+112.3%"},
                {"label": "Q1 互动增长", "value": "+123.7%"},
                {"label": "收藏驱动内容占比", "value": "34.9%"},
                {"label": "搜索承接强度", "value": "41.2/100"},
            ],
            "opportunities": [
                "音乐剧内容天然具备仪式感、出片感与情绪价值，适合高端护肤和香氛品牌绑定“场景消费”。",
                "高收藏笔记集中在攻略、OOTD、演前准备三类内容，说明品牌内容不仅能被看见，也能被留存。",
                "圈层讨论持续放大时，品牌若同步布局站内搜索与场景内容，能更快进入心智名单。",
            ],
        },
        "brand_status": {
            "kpi": [
                {"title": "品牌相关笔记", "display": "1,276"},
                {"title": "品牌互动总量", "display": "42.7万"},
                {"title": "品牌发声作者", "display": "1,038"},
                {"title": "搜索快照去重笔记", "display": "623"},
            ],
            "weekly": weekly_brand,
            "snapshot": [
                {"label": "主导内容类型", "value": "产品心得 · 46.8%"},
                {"label": "剧院场景内容占比", "value": "21.4%"},
                {"label": "搜索平均位次", "value": "32.4"},
                {"label": "Top10 占位率", "value": "12.7%"},
            ],
            "breakdown": [
                {"label": "产品词内容占比", "value": "64.2%"},
                {"label": "场景词内容占比", "value": "23.8%"},
                {"label": "高收藏笔记占比", "value": "31.8%"},
                {"label": "求购/种草意向占比", "value": "18.4%"},
            ],
            "takeaway": "雅顿已经进入圈层讨论，但当前更像被评价的产品品牌，还没有成为被向往的剧院场景品牌。",
        },
        "health_overview": {
            "score": 74.8,
            "tier": "成长强势",
            "benchmark": "兰蔻",
            "gap": -8.4,
            "dimensions": [
                {"name": "内容声量变化", "score": 70.0},
                {"name": "角色互动效率", "score": 76.0},
                {"name": "内容生态结构", "score": 68.0},
                {"name": "互动质量评分", "score": 77.0},
                {"name": "站内搜索表现", "score": 81.0},
                {"name": "种草与求购意向", "score": 77.0},
            ],
            "formula": [
                "总分由内容声量、角色效率、内容生态、互动质量、搜索表现、种草意向六个子维度标准化加权构成，满分 100。",
                "评分结果不只反映“被提及的多少”，更反映品牌在内容到搜索再到种草之间的完整度。",
                "竞品对标用于解释分差来源，帮助明确优先补足的短板维度。",
            ],
            "takeaway": "雅顿最强的是搜索与互动质量，最弱的是内容生态和声量持续性；品牌更容易被找到，但还不够容易被持续讨论与主动收藏。",
        },
        "voice_change": {
            "kpi": [
                {"title": "窗口内品牌笔记", "display": "1,276"},
                {"title": "周峰值笔记量", "display": "127"},
                {"title": "最新周互动", "display": "4.27万"},
                {"title": "Q1 声量增幅", "display": "+104.8%"},
            ],
            "weekly": weekly_brand,
            "growth": [
                {"label": "品牌词放量贡献", "value": "56%"},
                {"label": "产品词放量贡献", "value": "27%"},
                {"label": "场景词放量贡献", "value": "17%"},
                {"label": "峰值周收藏增幅", "value": "+33.4%"},
            ],
            "signals": [
                "Q1 内雅顿声量持续上行，但真正驱动增长的仍以品牌词和产品词为主。",
                "剧院场景词对增长的贡献仍偏低，说明品牌还没有把内容增长转化成文化认同增长。",
                "如果下一阶段补足场景词与高收藏内容，声量增长更容易沉淀成长期搜索资产。",
            ],
            "takeaway": "雅顿 Q1 声量总体保持上升，但增速主要来自品牌词与产品词放量，真正承接圈层文化的场景词占比仍偏低。",
        },
        "role_efficiency": {
            "kpi": [
                {"title": "篇均互动", "display": "334.5"},
                {"title": "最高效率人群", "display": "10k-100k"},
                {"title": "最高人群篇均互动", "display": "812.0"},
                {"title": "建议投放结构", "display": "4:6"},
            ],
            "rows": [
                {"name": "0-1k", "avg_inter": 96.0, "notes": 432},
                {"name": "1k-10k", "avg_inter": 248.0, "notes": 361},
                {"name": "10k-100k", "avg_inter": 812.0, "notes": 361},
                {"name": "100k+", "avg_inter": 624.0, "notes": 122},
            ],
            "mix": [
                {"label": "圈层发声者占比", "value": "38%"},
                {"label": "跨界种草机占比", "value": "62%"},
                {"label": "高互动作者集中层级", "value": "10k-100k"},
                {"label": "头部放大效率", "value": "次高"},
            ],
            "takeaway": "真正帮雅顿拉升效率的不是头部账号，而是既有审美表达又有可信分享感的中腰部创作者。",
        },
        "ecosystem": {
            "kpi": [
                {"title": "内容类型数", "display": "4"},
                {"title": "主导类型", "display": "产品心得"},
                {"title": "生态多样性指数", "display": "66.2"},
                {"title": "高转化类型", "display": "OOTD/打卡"},
            ],
            "types": [
                {"name": "产品心得", "notes": 597, "share": 46.8, "avg_inter": 286.0, "avg_save": 61.0},
                {"name": "攻略/清单", "notes": 253, "share": 19.8, "avg_inter": 338.0, "avg_save": 88.0},
                {"name": "OOTD/打卡", "notes": 211, "share": 16.5, "avg_inter": 624.0, "avg_save": 132.0},
                {"name": "Repo/复盘", "notes": 215, "share": 16.9, "avg_inter": 301.0, "avg_save": 57.0},
            ],
            "formulas": [
                "OOTD/打卡：剧院外立面或座位区镜头 + 低饱和高级妆感 + 情绪型短文案。",
                "攻略/清单：演前 2 小时状态管理清单 + 高质感单品露出 + 收藏导向标题。",
                "Repo/复盘：剧后情绪延续 + 留香/妆面持久反馈 + 同款求购承接。",
            ],
            "gaps": [
                "产品心得占比过高，导致品牌在圈层中更像“被评价的产品”，而不是“剧院生活方式的一部分”。",
                "高互动的 OOTD/打卡与高收藏的攻略/清单占比仍然不够，内容生态的场景面尚未铺开。",
                "下一阶段最该补的是兼具情绪价值和收藏价值的中段内容，而不是继续堆纯产品说明。",
            ],
            "takeaway": "产品心得占比过高，说明雅顿在圈层中更多被当作产品，而不是剧院生活方式的一部分。",
        },
        "quality": {
            "kpi": [
                {"title": "篇均收藏", "display": "76.2"},
                {"title": "篇均评论", "display": "11.4"},
                {"title": "互动质量指数", "display": "56.8"},
                {"title": "收藏驱动贡献", "display": "56%"},
            ],
            "rows": [
                {"name": "收藏/篇", "value": 76.2},
                {"name": "评论/篇", "value": 11.4},
                {"name": "分享/篇", "value": 6.8},
            ],
            "benchmark_rows": [
                {"name": "兰蔻", "value": 63.4, "aux": "质量指数领先，强在高收藏与高评论双高"},
                {"name": "雅诗兰黛", "value": 60.8, "aux": "稳定型质量资产，评论层更强"},
                {"name": "伊丽莎白雅顿", "value": 56.8, "aux": "收藏能力不错，但缺少连续爆点"},
                {"name": "YSL", "value": 58.2, "aux": "高话题感但收藏沉淀略弱"},
            ],
            "takeaway": "雅顿不缺能被收藏的内容，但高质量内容分布偏散，还没有形成稳定可复制的内容方法论。",
        },
        "search": {
            "kpi": [
                {"title": "去重搜索笔记", "display": "623"},
                {"title": "平均搜索位次", "display": "32.4"},
                {"title": "Top10 占位率", "display": "12.7%"},
                {"title": "搜索效率排名", "display": "#3/6"},
            ],
            "rows": [
                {"name": "兰蔻", "value": 1185, "aux": "Top10 15.8% · AvgRank 41.7"},
                {"name": "雅诗兰黛", "value": 1104, "aux": "Top10 14.6% · AvgRank 38.5"},
                {"name": "YSL", "value": 973, "aux": "Top10 13.9% · AvgRank 39.1"},
                {"name": "伊丽莎白雅顿", "value": 623, "aux": "Top10 12.7% · AvgRank 32.4"},
                {"name": "海蓝之谜", "value": 418, "aux": "Top10 11.9% · AvgRank 35.8"},
                {"name": "赫莲娜", "value": 377, "aux": "Top10 10.4% · AvgRank 37.6"},
            ],
            "keyword_rows": [
                {"name": "品牌词", "value": 100.0, "aux": "搜索承接最强，但竞争也最集中"},
                {"name": "产品词", "value": 74.0, "aux": "橘灿、金胶等单品具备承接空间"},
                {"name": "场景词", "value": 41.0, "aux": "剧院、演前、出片等词仍有明显空位"},
            ],
            "opportunities": [
                "雅顿在搜索效率上并不吃亏，说明品牌已经具备被找得到的基础。",
                "真正需要补的是搜索后的内容资产厚度，否则可见度难以转成长期心智。",
                "下一阶段最值得抢的是“剧院妆护”“演前状态”“剧后留香”等场景词搜索位。",
            ],
            "takeaway": "雅顿在搜索效率上并不吃亏，但搜索承接之后的内容资产厚度不足，可见度还难以转成长效心智。",
        },
        "voc": {
            "kpi": [
                {"title": "求购/种草占比", "display": "18.4%"},
                {"title": "复购/爱用占比", "display": "11.2%"},
                {"title": "高意向诉求数", "display": "576"},
                {"title": "可转译品牌表达", "display": "强"},
            ],
            "rows": [
                {"name": "求同款/链接", "value": 235},
                {"name": "种草/想买", "value": 198},
                {"name": "回购/爱用", "value": 143},
            ],
            "expressions": [
                {"label": "高频需求 01", "value": "演前状态在线"},
                {"label": "高频需求 02", "value": "剧院氛围感留香"},
                {"label": "高频需求 03", "value": "演后不垮妆、不疲态"},
                {"label": "高频需求 04", "value": "高级但不过分张扬"},
            ],
            "samples_by_group": voc_samples_by_group,
            "translations": [
                "品牌表达要从“功效说明”翻译成“场景状态管理”，更容易被圈层接受。",
                "最容易激发购买联想的不是专业术语，而是“质感、留香、状态在线、剧院灯光下也撑得住”这类表达。",
                "VOC 已经说明这群人会为带来仪式感和高级感的产品付费，不需要再做低价逻辑教育。",
            ],
            "takeaway": "音乐剧人群对“质感、留香、舞台前后状态管理”类表达最容易产生购买联想。",
        },
        "benchmark": {
            "kpi": [
                {"title": "当前标杆", "display": "兰蔻"},
                {"title": "雅顿排名", "display": "#3/6"},
                {"title": "与标杆差距", "display": "-8.4分"},
            ],
            "rows": [
                {"name": "兰蔻", "score": 83.2, "voice": 1820, "search": 1185, "quality": 63.4, "search_share": 15.8},
                {"name": "雅诗兰黛", "score": 77.9, "voice": 1654, "search": 1104, "quality": 60.8, "search_share": 14.6},
                {"name": "伊丽莎白雅顿", "score": 74.8, "voice": 1276, "search": 623, "quality": 56.8, "search_share": 12.7},
                {"name": "YSL", "score": 73.4, "voice": 1496, "search": 973, "quality": 58.2, "search_share": 13.9},
                {"name": "海蓝之谜", "score": 69.8, "voice": 918, "search": 418, "quality": 55.4, "search_share": 11.9},
                {"name": "赫莲娜", "score": 68.3, "voice": 842, "search": 377, "quality": 54.1, "search_share": 10.4},
            ],
            "gap_snapshot": [
                {"label": "与标杆差距最大维度", "value": "内容声量变化"},
                {"label": "次大差距维度", "value": "内容生态结构"},
                {"label": "雅顿领先维度", "value": "搜索效率"},
                {"label": "最易追平维度", "value": "互动质量"},
            ],
            "takeaway": "雅顿与头部竞品的差距不在单点效率，而在是否建立了足够完整、足够连续的圈层内容生态。",
        },
        "audience": {
            "kpi": [
                {"title": "圈层契合指数", "display": "78.5/100"},
                {"title": "高客单信号占比", "display": "42.0%"},
                {"title": "购买意向语句占比", "display": "19.3%"},
                {"title": "高端场景强度", "display": "84.0"},
            ],
            "traits": [
                {"name": "审美质感敏感", "score": 86.0},
                {"name": "细节考究", "score": 81.0},
                {"name": "精神悦己", "score": 77.0},
                {"name": "场景消费", "score": 74.0},
            ],
            "scenes": [
                {"name": "演前妆护准备", "score": 88.0},
                {"name": "剧院社交出片", "score": 84.0},
                {"name": "演后复盘分享", "score": 75.0},
                {"name": "异地巡演出行", "score": 69.0},
            ],
            "interests": [
                {"name": "精品咖啡", "score": 82.0},
                {"name": "沙龙香水", "score": 79.0},
                {"name": "看展", "score": 74.0},
                {"name": "酒店度假", "score": 68.0},
            ],
            "translations": [
                "对雅顿而言，这群人最值得沟通的不是“功能性”，而是“在重要场合保持状态和质感”。",
                "香氛、急救修护、抗老精华都能被翻译成剧院语境下的自我表达，而不是单纯产品卖点。",
                "内容上要少做教育式解释，多做具有光影氛围和细节质感的场景呈现。",
            ],
            "takeaway": "这群人不是泛娱乐流量，而是典型的高审美、高细节、高客单的场景消费人群。",
        },
        "diagnosis": {
            "kpi": [
                {"title": "可立即放大的优势", "display": "搜索表现"},
                {"title": "最紧迫短板", "display": "内容生态"},
                {"title": "首要动作", "display": "场景化补量"},
                {"title": "建议节奏", "display": "90 天三阶段"},
            ],
            "positives": [
                "雅顿在搜索承接和高意向内容上的基础已经足够支撑投放起量。",
                "剧院场景与雅顿的香氛、修护、抗老产品线天然适配。",
                "中腰部作者对雅顿的内容效率明显高于平均水平。",
            ],
            "risks": [
                "如果继续让产品心得型内容占主导，品牌会停留在“被提及”而不是“被向往”。",
                "单纯堆品牌词会抬高可见度，但不会自动形成圈层文化认同。",
                "达人只投泛美妆会损失音乐剧圈层的专业背书感。",
            ],
            "actions": [
                "把剧场前后 48 小时做成固定内容框架，承接香氛、修护、急救三类需求。",
                "用圈层发声者建立专业感，再用穿搭/香氛博主放大场景种草。",
                "所有内容复盘优先看收藏、搜索与私信求链接，而不是只看点赞。",
            ],
            "milestones": [
                {"label": "第 1 阶段", "value": "打透演前状态管理"},
                {"label": "第 2 阶段", "value": "放大剧院氛围种草"},
                {"label": "第 3 阶段", "value": "沉淀搜索与收藏资产"},
                {"label": "核心 KPI", "value": "收藏率、搜索位、求链率"},
            ],
            "takeaway": "雅顿具备进入音乐剧高端人群的资格，但想真正完成品牌跃迁，必须从产品讨论升级到场景心智。",
        },
    }


def _render_kpi_cards(items: list[dict[str, Any]]) -> str:
    return "".join(
        (
            "<article class=\"card stat-card\">"
            f"<div class=\"card-title\">{_escape(item.get('title', '-'))}</div>"
            f"<div class=\"card-value mono\">{_escape(item.get('display', '-'))}</div>"
            "</article>"
        )
        for item in items
    )


def _render_list(items: list[str], ordered: bool = False) -> str:
    tag = "ol" if ordered else "ul"
    if not items:
        items = ["-"]
    rows = "".join(f"<li>{_escape(item)}</li>" for item in items)
    return f"<{tag} class=\"action-list\">{rows}</{tag}>"


def _render_snapshot_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        items = [{"label": "-", "value": "-"}]
    rows = []
    for item in items:
        rows.append(
            "<div class=\"kv-row\">"
            f"<div class=\"kv-key\">{_escape(item.get('label', '-'))}</div>"
            f"<div class=\"kv-value mono\">{_escape(item.get('value', '-'))}</div>"
            "</div>"
        )
    return "".join(rows)


def _render_text_panels(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<div class=\"empty-box\">-</div>"
    cards = []
    for item in items:
        cards.append(
            "<article class=\"card micro-card\">"
            f"<div class=\"card-title\">{_escape(item.get('label', '-'))}</div>"
            f"<div class=\"card-value mono\">{_escape(item.get('value', '-'))}</div>"
            "</article>"
        )
    return "<div class=\"grid2\">" + "".join(cards) + "</div>"


def _render_weekly_bars(rows: list[dict[str, Any]], key: str) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    values = [float(item.get(key) or 0) for item in rows]
    max_value = max(values) if values else 1.0
    bars = []
    for row in rows:
        value = float(row.get(key) or 0)
        height = 18 if max_value <= 0 else max(18, int(value / max_value * 140))
        bars.append(
            "<div class=\"week-bar\">"
            f"<div class=\"week-bar-fill\" style=\"height:{height}px\"></div>"
            f"<div class=\"week-bar-num mono\">{_escape(_fmt_short(value))}</div>"
            f"<div class=\"week-bar-label mono\">{_escape(row.get('label', '-'))}</div>"
            "</div>"
        )
    return "<div class=\"week-chart\">" + "".join(bars) + "</div>"


def _render_bar_rows(rows: list[dict[str, Any]], value_key: str, extra_key: str | None = None) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    numeric_values = [float(item.get(value_key) or 0) for item in rows if item.get(value_key) is not None]
    max_value = max(numeric_values) if numeric_values else 1.0
    html_rows = []
    for item in rows:
        value = _to_float(item.get(value_key))
        width = 0 if value is None or max_value <= 0 else int(value / max_value * 100)
        if value is None:
            value_display = "-"
        elif float(value).is_integer():
            value_display = _fmt_num(value)
        else:
            value_display = _fmt_score(value, 1)
        extra = ""
        if extra_key and item.get(extra_key) is not None:
            extra = f"<span class=\"bar-extra\">样本 {item.get(extra_key)}</span>"
        aux = item.get("aux")
        aux_html = f"<div class=\"bar-aux\">{_escape(aux)}</div>" if aux else extra
        html_rows.append(
            "<div class=\"score-bar-row\">"
            "<div class=\"score-bar-main\">"
            f"<div class=\"score-bar-name\">{_escape(item.get('name', '-'))}</div>"
            f"{aux_html}"
            "</div>"
            "<div class=\"score-bar-track\">"
            f"<div class=\"score-bar-fill\" style=\"width:{width}%\"></div>"
            "</div>"
            f"<div class=\"score-bar-value mono\">{_escape(value_display)}</div>"
            "</div>"
        )
    return "".join(html_rows)


def _render_type_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    cards = []
    for index, item in enumerate(rows[:4]):
        color_class = "blue" if index == 0 else "amber" if index == 1 else "teal" if index == 2 else ""
        cards.append(
            f"<article class=\"card type-card {color_class}\">"
            f"<div class=\"card-title\">{_escape(item.get('name', '-'))}</div>"
            f"<div class=\"type-meta mono\">占比 {_escape(_fmt_pct(item.get('share'), 1))} · 样本 {_escape(_fmt_num(item.get('notes')))}</div>"
            f"<div class=\"type-grid-mini\">"
            f"<div><div class=\"mini-label\">篇均互动</div><div class=\"mini-value mono\">{_escape(_fmt_score(item.get('avg_inter'), 1))}</div></div>"
            f"<div><div class=\"mini-label\">篇均收藏</div><div class=\"mini-value mono\">{_escape(_fmt_score(item.get('avg_save'), 1))}</div></div>"
            "</div>"
            "</article>"
        )
    return "".join(cards)


def _render_rival_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    numeric_values = [float(item.get("score") or 0) for item in rows if item.get("score") is not None]
    max_value = max(numeric_values) if numeric_values else 1.0
    html_rows = []
    for item in rows:
        score = _to_float(item.get("score"))
        width = 0 if score is None or max_value <= 0 else int(score / max_value * 100)
        detail = (
            f"声量 {_fmt_num(item.get('voice'))} · 搜索 {_fmt_num(item.get('search'))} · "
            f"质量 {_fmt_score(item.get('quality'), 1)} · Top10 {_fmt_pct(item.get('search_share'), 1)}"
        )
        html_rows.append(
            "<div class=\"score-bar-row rival-row\">"
            "<div class=\"score-bar-main\">"
            f"<div class=\"score-bar-name\">{_escape(item.get('name', '-'))}</div>"
            f"<div class=\"bar-aux\">{_escape(detail)}</div>"
            "</div>"
            "<div class=\"score-bar-track\">"
            f"<div class=\"score-bar-fill\" style=\"width:{width}%\"></div>"
            "</div>"
            f"<div class=\"score-bar-value mono\">{_escape(_fmt_score(score, 1) if score is not None else '-')}</div>"
            "</div>"
        )
    return "".join(html_rows)


def _render_interest_chips(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<span class=\"interest-chip\">-</span>"
    return "".join(
        (
            "<span class=\"interest-chip\">"
            f"{_escape(item.get('name', '-'))} · {_escape(_fmt_score(item.get('score'), 1))}"
            "</span>"
        )
        for item in rows
    )


def _render_health_dimension_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    max_value = max(float(item.get("score") or 0) for item in rows) or 1.0
    parts = []
    for item in rows:
        score = _to_float(item.get("score"))
        width = 0 if score is None else int(score / max_value * 100)
        parts.append(
            "<div class=\"score-bar-row\">"
            "<div class=\"score-bar-main\">"
            f"<div class=\"score-bar-name\">{_escape(item.get('name', '-'))}</div>"
            "</div>"
            "<div class=\"score-bar-track\">"
            f"<div class=\"score-bar-fill\" style=\"width:{width}%\"></div>"
            "</div>"
            f"<div class=\"score-bar-value mono\">{_escape(_fmt_score(score, 1) if score is not None else '-')}</div>"
            "</div>"
        )
    return "".join(parts)


def _render_voc_sample_groups(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return "<div class=\"empty-box\">-</div>"
    cards: list[str] = []
    for group in groups:
        items = group.get("items") or []
        rows: list[str] = []
        if not items:
            rows.append("<div class=\"empty-box\">该分类暂无可展示样本</div>")
        for item in items:
            display_text = item.get("display_text") or "-"
            summary = item.get("summary") or ""
            meta = f"{item.get('author_nickname', '-')} · {item.get('publish_time', '-')}"
            stats = f"互动 {item.get('interaction_total', '-')} · 收藏 {item.get('collection_count', '-')}"
            summary_html = f"<div class=\"sample-summary\">{_escape(summary)}</div>" if summary and summary != display_text else ""
            rows.append(
                "<article class=\"sample-row\">"
                "<div class=\"sample-copy\">"
                f"<div class=\"sample-title\">{_escape(display_text)}</div>"
                f"{summary_html}"
                f"<div class=\"sample-meta mono\">{_escape(meta)}</div>"
                f"<div class=\"sample-stats mono\">{_escape(stats)}</div>"
                "</div>"
                f"<a class=\"sample-link\" href=\"{_escape(item.get('post_url', '#'))}\" target=\"_blank\" rel=\"noreferrer\" aria-label=\"查看{_escape(display_text)}原文\">查看原文</a>"
                "</article>"
            )
        cards.append(
            "<article class=\"card voc-sample-card\">"
            f"<div class=\"card-title\">{_escape(group.get('name', '-'))}</div>"
            f"<div class=\"sample-group-desc\">{_escape(group.get('description', '-'))}</div>"
            f"<div class=\"sample-group-count mono\">样本 {_escape(_fmt_num(group.get('sample_count')))}</div>"
            f"<div class=\"sample-list\">{''.join(rows)}</div>"
            "</article>"
        )
    return "<div class=\"grid3 sample-grid\">" + "".join(cards) + "</div>"


def _section(
    *,
    anchor: str,
    kicker: str,
    title: str,
    desc: str,
    kpi_html: str,
    takeaway: str,
    body_html: str,
) -> str:
    return (
        f"<section class=\"section\" id=\"{_escape(anchor)}\">"
        f"<div class=\"section-kicker\">{_escape(kicker)}</div>"
        f"<h2>{_escape(title)}</h2>"
        f"<p class=\"section-desc\">{_escape(desc)}</p>"
        f"<div class=\"grid4\">{kpi_html}</div>"
        f"<div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\">{_escape(takeaway)}</div></div>"
        f"{body_html}"
        "</section>"
    )


def _html(report: dict[str, Any]) -> str:
    meta = report["meta"]
    executive = report["executive"]
    health = report["health_overview"]
    score_display = _fmt_score(health.get("score"), 1) if health.get("score") is not None else "-"
    nav_score = score_display if score_display != "-" else "-"

    market = report["market_value"]
    brand_status = report["brand_status"]
    voice = report["voice_change"]
    role = report["role_efficiency"]
    ecosystem = report["ecosystem"]
    quality = report["quality"]
    search = report["search"]
    voc = report["voc"]
    benchmark = report["benchmark"]
    audience = report["audience"]
    diagnosis = report["diagnosis"]

    toc_items = [
        ("cover", "封面"),
        ("executive", "执行摘要"),
        ("market-value", "01 · 音乐剧圈层商业价值"),
        ("brand-status", "02 · 雅顿品牌现状"),
        ("health-overview", "03 · 健康度评分体系"),
        ("voice-change", "3.1 内容声量变化"),
        ("role-efficiency", "3.2 角色互动效率"),
        ("ecosystem", "3.3 内容生态结构"),
        ("quality", "3.4 互动质量评分"),
        ("search", "3.5 站内搜索表现"),
        ("voc", "3.6 种草与求购意向"),
        ("benchmark", "3.7 核心竞品对标"),
        ("audience", "04 · 目标受众洞察"),
        ("diagnosis", "05 · 品牌健康度诊断"),
    ]

    toc_html = []
    toc_html.append("<li class=\"toc-part\">封面 · 执行摘要</li>")
    for anchor, label in toc_items[:2]:
        toc_html.append(f"<li><a href=\"#{_escape(anchor)}\">{_escape(label)}</a></li>")
    toc_html.append("<li class=\"toc-part\">第一部分 · 平台与品牌现状</li>")
    for anchor, label in toc_items[2:4]:
        toc_html.append(f"<li><a href=\"#{_escape(anchor)}\">{_escape(label)}</a></li>")
    toc_html.append("<li class=\"toc-part\">第二部分 · 健康度评分</li>")
    for anchor, label in toc_items[4:12]:
        toc_html.append(f"<li><a href=\"#{_escape(anchor)}\">{_escape(label)}</a></li>")
    toc_html.append("<li class=\"toc-part\">第三部分 · 受众洞察</li>")
    toc_html.append(f"<li><a href=\"#audience\">04 · 目标受众洞察</a></li>")
    toc_html.append("<li class=\"toc-part\">第四部分 · 结论</li>")
    toc_html.append(f"<li><a href=\"#diagnosis\">05 · 品牌健康度诊断</a></li>")

    executive_anchor_html = ""
    if executive.get("anchors"):
        executive_anchor_html = (
            "<div class=\"card section-grid-gap\">"
            "<div class=\"card-title\">增长锚点</div>"
            f"{_render_text_panels(executive.get('anchors', []))}"
            "</div>"
        )
    executive_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card blue\"><div class=\"card-title\">三条核心结论</div>{_render_list(executive.get('findings', []))}</div>"
        f"<div class=\"card amber\"><div class=\"card-title\">Top 3 动作</div>{_render_list(executive.get('actions', []), ordered=True)}</div>"
        "</div>"
        f"{executive_anchor_html}"
    )

    market_support_html = ""
    if market.get("support"):
        market_support_html = (
            f"<div class=\"card\"><div class=\"card-title\">增长证据</div>{_render_snapshot_rows(market.get('support', []))}</div>"
        )
    market_opportunity_html = ""
    if market.get("opportunities"):
        market_opportunity_html = (
            f"<div class=\"card amber\"><div class=\"card-title\">机会判断</div>{_render_list(market.get('opportunities', []))}</div>"
        )
    market_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">Q1 周度热度走势</div>{_render_weekly_bars(market.get('weekly', []), 'notes')}</div>"
        f"<div class=\"card\"><div class=\"card-title\">Q1 周度互动走势</div>{_render_weekly_bars(market.get('weekly', []), 'interactions')}</div>"
        f"{market_support_html}"
        f"<div class=\"card\"><div class=\"card-title\">商业价值信号</div><div class=\"pull-quote\">{_escape(market.get('callout', '-'))}</div></div>"
        "</div>"
        f"<div class=\"section-grid-gap\">{market_opportunity_html}</div>"
    )
    brand_breakdown_html = ""
    if brand_status.get("breakdown"):
        brand_breakdown_html = f"<div class=\"card\"><div class=\"card-title\">品牌结构拆解</div>{_render_snapshot_rows(brand_status.get('breakdown', []))}</div>"
    brand_weekly_html = ""
    if brand_status.get("weekly"):
        brand_weekly_html = f"<div class=\"card\"><div class=\"card-title\">品牌周度声量</div>{_render_weekly_bars(brand_status.get('weekly', []), 'notes')}</div>"
    brand_status_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"{brand_weekly_html}"
        f"<div class=\"card\"><div class=\"card-title\">品牌快照</div>{_render_snapshot_rows(brand_status.get('snapshot', []))}</div>"
        f"{brand_breakdown_html}"
        f"<div class=\"card\"><div class=\"card-title\">现状判断</div><div class=\"pull-quote\">{_escape(brand_status.get('takeaway', '-'))}</div></div>"
        "</div>"
    )
    health_body = (
        "<div class=\"grid2 section-grid-gap\">"
        "<div class=\"card\">"
        "<div class=\"card-title\">六维得分</div>"
        f"{_render_health_dimension_rows(health.get('dimensions', []))}"
        "</div>"
        "<div class=\"card\">"
        "<div class=\"card-title\">评分口径</div>"
        f"{_render_list(health.get('formula', []))}"
        "</div>"
        "</div>"
    )
    voice_growth_html = ""
    if voice.get("growth"):
        voice_growth_html = f"<div class=\"card\"><div class=\"card-title\">增长拆解</div>{_render_snapshot_rows(voice.get('growth', []))}</div>"
    voice_signal_html = ""
    if voice.get("signals"):
        voice_signal_html = f"<div class=\"card amber\"><div class=\"card-title\">增长判断</div>{_render_list(voice.get('signals', []))}</div>"
    voice_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">品牌声量周变化</div>{_render_weekly_bars(voice.get('weekly', []), 'notes')}</div>"
        f"<div class=\"card\"><div class=\"card-title\">互动周变化</div>{_render_weekly_bars(voice.get('weekly', []), 'interactions')}</div>"
        f"{voice_growth_html}"
        f"{voice_signal_html}"
        "</div>"
    )
    role_mix_html = ""
    if role.get("mix"):
        role_mix_html = f"<div class=\"card\"><div class=\"card-title\">投放结构判断</div>{_render_snapshot_rows(role.get('mix', []))}</div>"
    role_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">不同角色层级的互动效率</div>{_render_bar_rows(role.get('rows', []), 'avg_inter', 'notes')}</div>"
        f"{role_mix_html}"
        "</div>"
    )
    ecosystem_formula_html = ""
    if ecosystem.get("formulas"):
        ecosystem_formula_html = f"<div class=\"card blue\"><div class=\"card-title\">高转化内容公式</div>{_render_list(ecosystem.get('formulas', []))}</div>"
    ecosystem_gap_html = ""
    if ecosystem.get("gaps"):
        ecosystem_gap_html = f"<div class=\"card amber\"><div class=\"card-title\">生态缺口</div>{_render_list(ecosystem.get('gaps', []))}</div>"
    ecosystem_body = (
        "<div class=\"type-wrap section-grid-gap\">"
        f"{_render_type_cards(ecosystem.get('types', []))}"
        "</div>"
        "<div class=\"grid2 section-grid-gap\">"
        f"{ecosystem_formula_html}"
        f"{ecosystem_gap_html}"
        "</div>"
    )
    quality_benchmark_html = ""
    if quality.get("benchmark_rows"):
        quality_benchmark_html = f"<div class=\"card\"><div class=\"card-title\">竞品质量参照</div>{_render_bar_rows(quality.get('benchmark_rows', []), 'value')}</div>"
    quality_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">互动质量拆解</div>{_render_bar_rows(quality.get('rows', []), 'value')}</div>"
        f"{quality_benchmark_html}"
        "</div>"
    )
    search_keyword_html = ""
    if search.get("keyword_rows"):
        search_keyword_html = f"<div class=\"card\"><div class=\"card-title\">关键词机会</div>{_render_bar_rows(search.get('keyword_rows', []), 'value')}</div>"
    search_opportunity_html = ""
    if search.get("opportunities"):
        search_opportunity_html = f"<div class=\"card amber\"><div class=\"card-title\">搜索动作建议</div>{_render_list(search.get('opportunities', []))}</div>"
    search_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">站内搜索快照对比</div>{_render_bar_rows(search.get('rows', []), 'value')}</div>"
        f"{search_keyword_html}"
        f"{search_opportunity_html}"
        "</div>"
    )
    voc_expression_html = ""
    if voc.get("expressions"):
        voc_expression_html = f"<div class=\"card\"><div class=\"card-title\">高频诉求表达</div>{_render_snapshot_rows(voc.get('expressions', []))}</div>"
    voc_samples_html = ""
    if voc.get("samples_by_group"):
        voc_samples_html = (
            "<div class=\"card section-grid-gap\">"
            "<div class=\"card-title\">PO 文事实样本</div>"
            f"{_render_voc_sample_groups(voc.get('samples_by_group', []))}"
            "</div>"
        )
    voc_translation_html = ""
    if voc.get("translations"):
        voc_translation_html = f"<div class=\"card amber\"><div class=\"card-title\">品牌表达转译</div>{_render_list(voc.get('translations', []))}</div>"
    voc_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">意向信号分布</div>{_render_bar_rows(voc.get('rows', []), 'value')}</div>"
        f"{voc_expression_html}"
        "</div>"
        f"{voc_samples_html}"
        f"<div class=\"section-grid-gap\">{voc_translation_html}</div>"
    )
    benchmark_gap_html = ""
    if benchmark.get("gap_snapshot"):
        benchmark_gap_html = f"<div class=\"card\"><div class=\"card-title\">差距来源</div>{_render_snapshot_rows(benchmark.get('gap_snapshot', []))}</div>"
    benchmark_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">核心竞品对标</div>{_render_rival_rows(benchmark.get('rows', []))}</div>"
        f"{benchmark_gap_html}"
        "</div>"
    )
    audience_translation_html = ""
    if audience.get("translations"):
        audience_translation_html = f"<div class=\"card amber\"><div class=\"card-title\">对雅顿的启示</div>{_render_list(audience.get('translations', []))}</div>"
    audience_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">受众特质画像</div>{_render_bar_rows(audience.get('traits', []), 'score')}</div>"
        f"<div class=\"card\"><div class=\"card-title\">关键消费场景</div>{_render_bar_rows(audience.get('scenes', []), 'score')}</div>"
        "</div>"
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card\"><div class=\"card-title\">跨兴趣匹配</div><div class=\"interest-wrap\">{_render_interest_chips(audience.get('interests', []))}</div></div>"
        f"{audience_translation_html}"
        "</div>"
    )
    diagnosis_milestones_html = ""
    if diagnosis.get("milestones"):
        diagnosis_milestones_html = f"<div class=\"card\"><div class=\"card-title\">90 天推进节奏</div>{_render_snapshot_rows(diagnosis.get('milestones', []))}</div>"
    diagnosis_body = (
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card blue\"><div class=\"card-title\">优势</div>{_render_list(diagnosis.get('positives', []))}</div>"
        f"<div class=\"card red\"><div class=\"card-title\">风险</div>{_render_list(diagnosis.get('risks', []))}</div>"
        "</div>"
        "<div class=\"grid2 section-grid-gap\">"
        f"<div class=\"card amber\"><div class=\"card-title\">下一步动作</div>{_render_list(diagnosis.get('actions', []), ordered=True)}</div>"
        f"{diagnosis_milestones_html}"
        "</div>"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>小红书 × BRAND HEALTH 雅顿品牌健康度洞察报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #09090f;
  --bg2: #111118;
  --bg3: #16161f;
  --bg4: #1d1d28;
  --line: rgba(255,255,255,0.06);
  --line2: rgba(255,255,255,0.10);
  --text: #e8e8f0;
  --text2: #9898b0;
  --text3: #5a5a72;
  --blue: #4f7dff;
  --blue2: #2a4fd4;
  --blue-g: rgba(79,125,255,0.12);
  --amber: #f5a623;
  --amber-g: rgba(245,166,35,0.10);
  --teal: #2dd4bf;
  --teal-g: rgba(45,212,191,0.10);
  --red: #ff5f6d;
  --red-g: rgba(255,95,109,0.10);
  --green: #22c55e;
  --purple: #a78bfa;
  --nav-w: 260px;
  --radius: 16px;
  --radius-sm: 10px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; color-scheme: dark; }}
body {{
  font-family: 'Sora', 'Noto Sans SC', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}}
a {{ text-decoration: none; color: inherit; }}
.skip-link {{
  position: absolute;
  left: 12px;
  top: -48px;
  background: #fff;
  color: #111;
  font-weight: 700;
  padding: 8px 10px;
  border-radius: 8px;
  z-index: 999;
}}
.skip-link:focus-visible {{ top: 12px; }}
.nav {{
  width: var(--nav-w);
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  background: var(--bg2);
  border-right: 1px solid var(--line);
  padding: 28px 16px 24px;
  z-index: 100;
  overflow-y: auto;
}}
.nav-brand {{
  background: linear-gradient(135deg, var(--blue2) 0%, #1a2880 100%);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  margin-bottom: 24px;
  border: 1px solid rgba(79,125,255,0.25);
}}
.nav-brand .nb-tag {{
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.55);
  font-family: 'DM Mono', monospace;
}}
.nav-brand .nb-name {{
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  margin-top: 4px;
  letter-spacing: -0.02em;
}}
.nav-brand .nb-sub {{
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-top: 6px;
}}
.nav-score-badge {{
  background: var(--bg3);
  border: 1px solid var(--line2);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.nsb-num {{
  font-size: 32px;
  font-weight: 800;
  color: var(--amber);
  font-family: 'DM Mono', monospace;
  line-height: 1;
}}
.nsb-label {{
  font-size: 10px;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}}
.nsb-tier {{
  font-size: 13px;
  font-weight: 600;
  color: var(--amber);
}}
.nav-toc {{ list-style: none; }}
.nav-toc li {{ margin: 2px 0; }}
.nav-toc a {{
  display: block;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--text2);
  transition: color .2s ease, background-color .2s ease, border-color .2s ease;
  border: 1px solid transparent;
}}
.nav-toc a:hover,
.nav-toc a:focus-visible,
.nav-toc a.active {{
  color: var(--blue);
  background: var(--blue-g);
  border-color: rgba(79,125,255,0.15);
  outline: 2px solid transparent;
}}
.nav-toc .toc-part {{
  font-size: 10px;
  font-family: 'DM Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text3);
  padding: 14px 12px 4px;
}}
.main {{ margin-left: var(--nav-w); min-height: 100vh; }}
.hero {{
  min-height: 100vh;
  background:
    radial-gradient(ellipse at 80% 20%, rgba(79,125,255,0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 10% 80%, rgba(245,166,35,0.07) 0%, transparent 45%),
    var(--bg);
  border-bottom: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 80px 64px 64px;
  position: relative;
  overflow: hidden;
}}
.hero-grid-bg {{
  position: absolute;
  inset: 0;
  opacity: 0.03;
  background-image:
    linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px);
  background-size: 40px 40px;
}}
.hero-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--blue-g);
  border: 1px solid rgba(79,125,255,0.25);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 11px;
  font-family: 'DM Mono', monospace;
  letter-spacing: 0.1em;
  color: var(--blue);
  text-transform: uppercase;
  margin-bottom: 28px;
}}
.hero-chip::before {{ content: '●'; font-size: 8px; }}
.hero h1 {{
  font-size: 60px;
  font-weight: 800;
  line-height: 1.02;
  letter-spacing: -0.04em;
  color: #fff;
  max-width: 760px;
  text-wrap: balance;
}}
.hero h1 span {{ color: var(--blue); }}
.hero-desc {{
  max-width: 760px;
  margin-top: 20px;
  font-size: 16px;
  color: var(--text2);
  line-height: 1.8;
}}
.hero-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 28px;
}}
.hero-tag {{
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--line2);
  color: var(--text2);
  font-family: 'DM Mono', monospace;
}}
.hero-stats {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 16px;
  margin-top: 40px;
  max-width: 760px;
}}
.hstat {{
  background: var(--bg3);
  border: 1px solid var(--line2);
  border-radius: var(--radius-sm);
  padding: 18px 20px;
}}
.hstat-num {{
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  font-family: 'DM Mono', monospace;
  letter-spacing: -0.03em;
}}
.hstat-label {{ font-size: 11px; color: var(--text3); margin-top: 4px; }}
.section {{
  padding: 72px 64px;
  border-bottom: 1px solid var(--line);
  scroll-margin-top: 24px;
}}
.section:last-child {{ border-bottom: none; }}
.section-kicker {{
  font-size: 11px;
  font-family: 'DM Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--blue);
  margin-bottom: 10px;
}}
.section h2 {{
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: #fff;
  margin-bottom: 10px;
  line-height: 1.2;
  text-wrap: balance;
}}
.section-desc {{
  font-size: 14px;
  color: var(--text2);
  max-width: 760px;
  line-height: 1.8;
  margin-bottom: 28px;
}}
.grid2 {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }}
.grid3 {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; }}
.grid4 {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }}
.section-grid-gap {{ margin-top: 16px; }}
.card {{
  background: var(--bg3);
  border: 1px solid var(--line2);
  border-radius: var(--radius);
  padding: 24px;
  min-width: 0;
}}
.micro-card {{
  padding: 18px;
  border-radius: 12px;
  background: var(--bg4);
}}
.micro-card .card-title {{
  margin-bottom: 8px;
}}
.micro-card .card-value {{
  font-size: 20px;
}}
.card.blue {{ border-color: rgba(79,125,255,0.25); background: rgba(79,125,255,0.06); }}
.card.amber {{ border-color: rgba(245,166,35,0.25); background: rgba(245,166,35,0.05); }}
.card.teal {{ border-color: rgba(45,212,191,0.2); background: rgba(45,212,191,0.05); }}
.card.red {{ border-color: rgba(255,95,109,0.2); background: rgba(255,95,109,0.05); }}
.card-title {{
  font-size: 13px;
  font-weight: 600;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}}
.card-value {{
  font-size: 26px;
  font-weight: 700;
  font-family: 'DM Mono', monospace;
  color: #fff;
}}
.insight-box {{
  background: var(--bg4);
  border-left: 3px solid var(--blue);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 14px 18px;
  margin-top: 18px;
}}
.ib-label {{
  font-size: 10px;
  font-family: 'DM Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text3);
  margin-bottom: 6px;
}}
.ib-text {{ font-size: 14px; color: var(--text); line-height: 1.7; }}
.mono {{ font-family: 'DM Mono', monospace; font-variant-numeric: tabular-nums; }}
.action-list {{ margin-left: 18px; }}
.action-list li {{ margin: 7px 0; color: #d8d8e8; }}
.kv-row {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}}
.kv-row:last-child {{ border-bottom: none; }}
.kv-key {{ color: var(--text2); min-width: 0; }}
.kv-value {{ color: #fff; text-align: right; min-width: 0; word-break: break-word; }}
.pull-quote {{
  font-size: 16px;
  line-height: 1.8;
  color: #fff;
}}
.week-chart {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(44px, 1fr));
  align-items: end;
  gap: 10px;
  min-height: 220px;
}}
.week-bar {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: end;
  min-width: 0;
}}
.week-bar-fill {{
  width: 100%;
  border-radius: 10px 10px 4px 4px;
  background: linear-gradient(180deg, var(--blue) 0%, var(--purple) 100%);
}}
.week-bar-num {{
  font-size: 10px;
  color: var(--text3);
  margin-top: 8px;
}}
.week-bar-label {{
  font-size: 10px;
  color: var(--text2);
  margin-top: 2px;
}}
.score-bar-row {{
  display: grid;
  grid-template-columns: minmax(160px, 230px) 1fr 76px;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}}
.score-bar-row:last-child {{ border-bottom: none; }}
.score-bar-main {{ min-width: 0; }}
.score-bar-name {{
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}}
.bar-aux {{
  font-size: 11px;
  color: var(--text3);
  margin-top: 2px;
  line-height: 1.5;
  word-break: break-word;
}}
.bar-extra {{
  font-size: 11px;
  color: var(--text3);
}}
.score-bar-track {{
  height: 10px;
  border-radius: 999px;
  background: var(--bg4);
  overflow: hidden;
}}
.score-bar-fill {{
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--blue), var(--purple));
}}
.score-bar-value {{
  font-size: 13px;
  color: #fff;
  text-align: right;
}}
.type-wrap {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 14px;
}}
.type-card .type-meta {{
  font-size: 12px;
  color: var(--text3);
  margin-bottom: 12px;
}}
.type-grid-mini {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0,1fr));
  gap: 12px;
}}
.mini-label {{
  font-size: 11px;
  color: var(--text3);
  margin-bottom: 4px;
}}
.mini-value {{
  font-size: 18px;
  color: #fff;
}}
.interest-wrap {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}}
.interest-chip {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--bg4);
  border: 1px solid var(--line2);
  color: #fff;
  font-size: 12px;
  font-family: 'DM Mono', monospace;
}}
.sample-grid {{
  align-items: start;
}}
.voc-sample-card {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.sample-group-desc {{
  font-size: 13px;
  color: var(--text2);
  line-height: 1.7;
}}
.sample-group-count {{
  font-size: 11px;
  color: var(--text3);
}}
.sample-list {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.sample-row {{
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}}
.sample-copy {{
  min-width: 0;
  flex: 1;
}}
.sample-title {{
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.sample-summary {{
  font-size: 12px;
  color: var(--text2);
  margin-top: 4px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.sample-meta, .sample-stats {{
  font-size: 11px;
  color: var(--text3);
  margin-top: 6px;
}}
.sample-link {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  border-radius: 999px;
  border: 1px solid rgba(79,125,255,0.25);
  background: var(--blue-g);
  color: var(--blue);
  padding: 8px 12px;
  font-size: 11px;
  font-family: 'DM Mono', monospace;
  transition: background-color .2s ease, color .2s ease, border-color .2s ease, transform .2s ease;
}}
.sample-link:hover,
.sample-link:focus-visible {{
  background: rgba(79,125,255,0.18);
  border-color: rgba(79,125,255,0.40);
  color: #dfe7ff;
  outline: 2px solid rgba(79,125,255,0.28);
  outline-offset: 2px;
}}
.sample-link:active {{
  transform: translateY(1px);
}}
.empty-box {{
  border: 1px dashed var(--line2);
  border-radius: 12px;
  padding: 18px;
  color: var(--text3);
}}
@media (max-width: 1280px) {{
  .section, .hero {{ padding-left: 36px; padding-right: 36px; }}
  .hero h1 {{ font-size: 48px; }}
  .type-wrap {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
}}
@media (max-width: 1080px) {{
  .nav {{ position: sticky; width: 100%; height: auto; max-height: 42vh; }}
  .main {{ margin-left: 0; }}
  .hero {{ min-height: auto; padding-top: 46px; }}
  .grid4 {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
  .grid3 {{ grid-template-columns: 1fr; }}
  .grid2 {{ grid-template-columns: 1fr; }}
  .type-wrap {{ grid-template-columns: 1fr; }}
  .score-bar-row {{ grid-template-columns: 1fr; }}
  .sample-row {{ flex-direction: column; }}
  .sample-link {{ width: 100%; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }}
}}
</style>
</head>
<body>
<a class="skip-link" href="#main">跳到正文</a>
<nav class="nav" aria-label="章节导航">
  <div class="nav-brand" translate="no">
    <div class="nb-tag">XHS Brand Health Report</div>
    <div class="nb-name">小红书 × BRAND HEALTH</div>
    <div class="nb-sub">雅顿 · {meta["report_period"]}</div>
  </div>
  <div class="nav-score-badge">
    <div class="nsb-num">{_escape(nav_score)}</div>
    <div>
      <div class="nsb-label">Health Score</div>
      <div class="nsb-tier">{_escape(health.get("tier", "-"))}</div>
    </div>
  </div>
  <ul class="nav-toc" id="toc">
    {''.join(toc_html)}
  </ul>
</nav>
<main class="main" id="main">
  <section class="hero" id="cover">
    <div class="hero-grid-bg" aria-hidden="true"></div>
    <div class="hero-chip">{_escape(executive.get("hero_chip", ""))}</div>
    <h1><span translate="no">雅顿</span>品牌健康度洞察报告</h1>
    <p class="hero-desc">{_escape(executive.get("summary", ""))}</p>
    <div class="hero-meta">
      <span class="hero-tag">平台：{_escape(meta['platform'])}</span>
      <span class="hero-tag">报告期：{_escape(meta['report_period'])}</span>
      <span class="hero-tag">数据口径：{_escape(meta['coverage'])}</span>
      <span class="hero-tag">生成时间：{_escape(meta['generated_at'].replace('T', ' '))}</span>
    </div>
    <div class="hero-stats">
      <div class="hstat"><div class="hstat-num mono">{_escape(executive['kpi'][0]['display'])}</div><div class="hstat-label">{_escape(executive['kpi'][0]['title'])}</div></div>
      <div class="hstat"><div class="hstat-num mono">{_escape(executive['kpi'][1]['display'])}</div><div class="hstat-label">{_escape(executive['kpi'][1]['title'])}</div></div>
      <div class="hstat"><div class="hstat-num mono">{_escape(executive['kpi'][2]['display'])}</div><div class="hstat-label">{_escape(executive['kpi'][2]['title'])}</div></div>
    </div>
  </section>
  {_section(anchor="executive", kicker="封面 · 执行摘要", title="执行摘要", desc="先给结论，再给证据。", kpi_html=_render_kpi_cards(executive["kpi"]), takeaway=executive["summary"], body_html=executive_body)}
  {_section(anchor="market-value", kicker="01 · 音乐剧圈层在小红书的商业价值", title="音乐剧圈层在小红书的商业价值", desc="圈层热度、互动密度与搜索承接都在放大。", kpi_html=_render_kpi_cards(market["kpi"]), takeaway=market["takeaway"], body_html=market_body)}
  {_section(anchor="brand-status", kicker="02 · 雅顿品牌现状", title="雅顿品牌现状", desc="品牌已经进入讨论，但尚未完成场景心智占位。", kpi_html=_render_kpi_cards(brand_status["kpi"]), takeaway=brand_status["takeaway"], body_html=brand_status_body)}
  {_section(anchor="health-overview", kicker="03 · 健康度评分体系", title="健康度评分体系", desc="六维拆解雅顿与标杆品牌的真实差距。", kpi_html=_render_kpi_cards([{"title": "健康度总分", "display": f"{_fmt_score(health.get('score'), 1)}/100" if health.get("score") is not None else "-"}, {"title": "健康度层级", "display": health.get("tier", "-")}, {"title": "标杆品牌", "display": health.get("benchmark", "-")}, {"title": "与标杆差距", "display": f"{_fmt_score(health.get('gap'), 1)}分" if health.get("gap") is not None else "-"}]), takeaway=health["takeaway"], body_html=health_body)}
  {_section(anchor="voice-change", kicker="3.1 · 内容声量变化", title="内容声量变化", desc="看品牌声量是否能持续增长并沉淀成场景认知。", kpi_html=_render_kpi_cards(voice["kpi"]), takeaway=voice["takeaway"], body_html=voice_body)}
  {_section(anchor="role-efficiency", kicker="3.2 · 角色互动效率", title="角色互动效率", desc="真正能拉高效率的是哪一层创作者。", kpi_html=_render_kpi_cards(role["kpi"]), takeaway=role["takeaway"], body_html=role_body)}
  {_section(anchor="ecosystem", kicker="3.3 · 内容生态结构", title="内容生态结构", desc="看雅顿能否同时覆盖高互动、高收藏和高向往内容。", kpi_html=_render_kpi_cards(ecosystem["kpi"]), takeaway=ecosystem["takeaway"], body_html=ecosystem_body)}
  {_section(anchor="quality", kicker="3.4 · 互动质量评分", title="互动质量评分", desc="互动不是只看总量，更要看内容是否值得被留存和传播。", kpi_html=_render_kpi_cards(quality["kpi"]), takeaway=quality["takeaway"], body_html=quality_body)}
  {_section(anchor="search", kicker="3.5 · 站内搜索表现", title="站内搜索表现", desc="搜索效率决定品牌能否被主动找到并进入决策链路。", kpi_html=_render_kpi_cards(search["kpi"]), takeaway=search["takeaway"], body_html=search_body)}
  {_section(anchor="voc", kicker="3.6 · 种草与求购意向（VOC）", title="种草与求购意向（VOC）", desc="看用户最愿意为哪些剧院场景表达买单。", kpi_html=_render_kpi_cards(voc["kpi"]), takeaway=voc["takeaway"], body_html=voc_body)}
  {_section(anchor="benchmark", kicker="3.7 · 核心竞品对标", title="核心竞品对标", desc="分差不只在总分，更在不同维度的资产厚度。", kpi_html=_render_kpi_cards(benchmark["kpi"]), takeaway=benchmark["takeaway"], body_html=benchmark_body)}
  {_section(anchor="audience", kicker="04 · 目标受众洞察", title="目标受众洞察", desc="这是一群高审美、高细节、高客单的场景消费人群。", kpi_html=_render_kpi_cards(audience["kpi"]), takeaway=audience["takeaway"], body_html=audience_body)}
  {_section(anchor="diagnosis", kicker="05 · 品牌健康度诊断", title="品牌健康度诊断", desc="把健康度结果直接转成雅顿可执行的 90 天动作。", kpi_html=_render_kpi_cards(diagnosis["kpi"]), takeaway=diagnosis["takeaway"], body_html=diagnosis_body)}
</main>
<script>
(() => {{
  const links = [...document.querySelectorAll('#toc a[href^="#"]')];
  const map = new Map(links.map((link) => [link.getAttribute('href').slice(1), link]));
  const sections = [...map.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  const observer = new IntersectionObserver((entries) => {{
    entries.forEach((entry) => {{
      const link = map.get(entry.target.id);
      if (!link) return;
      if (entry.isIntersecting) {{
        links.forEach((item) => item.classList.remove('active'));
        link.classList.add('active');
      }}
    }});
  }}, {{ rootMargin: '-35% 0px -55% 0px', threshold: 0.01 }});
  sections.forEach((section) => observer.observe(section));
}})();
</script>
</body>
</html>
"""


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html(report), encoding="utf-8")


def main() -> None:
    mock_report = _build_mock_report()
    real_report = _build_real_report()
    _write_report(MOCK_OUTPUT, mock_report)
    _write_report(REAL_OUTPUT, real_report)
    print(
        json.dumps(
            {
                "mock_output": str(MOCK_OUTPUT),
                "real_output": str(REAL_OUTPUT),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "mock_score": mock_report["health_overview"]["score"],
                "real_score": real_report["health_overview"]["score"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
