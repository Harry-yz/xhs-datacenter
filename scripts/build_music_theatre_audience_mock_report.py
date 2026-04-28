from __future__ import annotations

import html
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db import SessionLocal

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "docs/reports/music_theatre_audience_mock_90d.html"
WINDOW_DAYS = 90
TODAY = datetime.now().date()
START_DATE = TODAY - timedelta(days=WINDOW_DAYS - 1)

MUSIC_REGEX = r"(音乐剧|剧院|卡司|repo|返场|二刷|法扎|德扎|魅影|musical|broadway|west\s*end|伦敦西区|sd|stage door|巡演|选座|抢票|票档|末场|一巡|音乐剧演员)"

CONTENT_GROUPS: list[dict[str, str]] = [
    {
        "name": "OOTD / 剧院打卡",
        "pattern": r"(ootd|穿搭|妆容|look|打卡|拍照|出片|dress code|剧院感)",
        "description": "围绕观演穿搭、妆造、剧院空间和出片氛围的内容，是最强的自我呈现场景。",
    },
    {
        "name": "Repo / 卡司复盘",
        "pattern": r"(\brepo\b|返场|二刷|卡司|唱段|舞台|末场|\bsd\b|stage door|谢幕)",
        "description": "高情绪密度、高圈层认同的深度内容，决定谁在定义圈层语言和审美。",
    },
    {
        "name": "观演攻略 / 选座",
        "pattern": r"(攻略|选座|怎么买|抢票|票档|座位|防雷|观演须知|一刷)",
        "description": "工具属性最强、收藏最高的内容，最接近用户的实际决策行为。",
    },
    {
        "name": "巡演记录 / 城市流动",
        "pattern": r"(巡演|上海站|北京站|南京站|深圳站|高铁|酒店|跨城|异地)",
        "description": "把音乐剧从作品消费延展成赴约、出门和重要夜晚安排的场景内容。",
    },
]

TOPIC_GROUPS: list[dict[str, str]] = [
    {"name": "作品/IP 讨论", "pattern": r"(法扎|德扎|魅影|伊丽莎白|摇滚莫扎特|hamilton|wicked|mamma mia|剧目|原卡|中文版)"},
    {"name": "卡司 / 演员", "pattern": r"(卡司|演员|主演|替卡|末卡|官宣|返场|\bsd\b|stage door)"},
    {"name": "剧场体验", "pattern": r"(剧院|视角|舞台|灯光|音响|现场|氛围|谢幕|返场)"},
    {"name": "穿搭妆造 / 出片", "pattern": r"(ootd|穿搭|妆容|出片|look|拍照|造型|dress code)"},
    {"name": "票务 / 选座", "pattern": r"(买票|抢票|票档|选座|座位|开票|蹲票|溢价)"},
    {"name": "赴约 / 重要夜晚", "pattern": r"(巡演|上海站|北京站|异地|高铁|赴约|夜晚|约会|散场|晚场)"},
    {"name": "谷子 / 周边收藏", "pattern": r"(谷子|周边|票根|明信片|徽章|海报|收藏)"},
]

NEED_GROUPS: list[dict[str, str]] = [
    {
        "name": "演前准备",
        "pattern": r"(买票|抢票|票档|选座|座位|预算|dress code|着装|妆容|准备|提前|入场)",
        "description": "从选座到着装妆容，用户会在演前集中完成重要场合准备。",
    },
    {
        "name": "演中呈现",
        "pattern": r"(出片|拍照|穿搭|妆容|打卡|剧院|look|状态|体面|光影)",
        "description": "观演当下的自我呈现、出片状态和体面感表达。",
    },
    {
        "name": "演后余韵",
        "pattern": r"(\brepo\b|返场|二刷|哭|上头|封神|安利|后劲|修护|卸妆|情绪)",
        "description": "散场后的情绪复盘、自我照顾与修护延续。",
    },
]

CULTURE_TERMS: list[dict[str, str]] = [
    {"term": "卡司", "meaning": "演员阵容与排期，是圈层最核心的信息节点。", "pattern": r"卡司"},
    {"term": "Repo", "meaning": "观演复盘和情绪记录，是音乐剧人群最重要的表达方式之一。", "pattern": r"\brepo\b"},
    {"term": "SD", "meaning": "Stage Door，散场后和演员互动，是重要的仪式感场景。", "pattern": r"(\bsd\b|stage door)"},
    {"term": "二刷", "meaning": "重复观演，代表用户已经从兴趣进入高黏性阶段。", "pattern": r"二刷"},
    {"term": "返场", "meaning": "演出结束后的加演或谢幕互动，也是情绪峰值时刻。", "pattern": r"返场"},
    {"term": "谷子", "meaning": "周边、收藏物，是作品热爱外化成消费的表现。", "pattern": r"谷子"},
    {"term": "末场", "meaning": "最后一场演出，情绪和稀缺性通常最高。", "pattern": r"末场"},
]

TABOO_HINTS: list[str] = [
    "反感外行式居高临下解释，圈层更接受内行视角和细节尊重。",
    "不喜欢生硬蹭热度，尤其讨厌只借剧目名做表层联名。",
    "剧透、拉踩卡司和低质玩梗都容易被认为不懂圈层文化。",
]

CROSS_INTERESTS: list[dict[str, str]] = [
    {"name": "穿搭妆造", "pattern": r"(穿搭|ootd|look|妆容|妆发|造型|dress code|口红|眼妆)"},
    {"name": "重要夜晚", "pattern": r"(约会|晚场|夜晚|赴约|重要场合|夜景|散场|演前)"},
    {"name": "状态管理", "pattern": r"(状态|气色|上镜|精致|体面|准备好|在线|补妆|修护)"},
    {"name": "香氛 / 留香", "pattern": r"(香水|留香|木质香|沙龙香|香氛)"},
    {"name": "体面感表达", "pattern": r"(体面|得体|松弛|高级感|氛围感|质感)"},
    {"name": "出片氛围", "pattern": r"(出片|拍照|光影|剧院感|氛围|打卡)"},
]

HIGH_VALUE_PATTERNS = [
    ("高审美质感", r"(质感|氛围|高级|审美|光影|仪式感)"),
    ("情绪浓度", r"(上头|封神|哭|后劲|震撼|心碎|哽咽)"),
    ("社交表达", r"(搭子|同好|约看|出片|打卡|分享)"),
    ("实用决策", r"(攻略|选座|票档|怎么买|防雷|清单)"),
]

BEAUTY_SCENE_REGEX = re.compile(
    r"(妆容|妆发|穿搭|ootd|look|出片|拍照|打卡|赴约|重要场合|夜晚|状态|气色|体面|精致|修护|卸妆|留香|香氛|光影)",
    re.IGNORECASE,
)


@dataclass
class NoteRow:
    note_id: str
    title: str
    content: str
    text: str
    search_keyword: str
    post_url: str
    publish_time: datetime | None
    interaction_total: int
    collection_count: int
    comment_count: int
    stat_count: int
    author_id: str
    author_nickname: str
    author_fans_count: int


@dataclass
class CreatorRow:
    author_id: str
    nickname: str
    fans_count: int
    note_count: int
    interaction_total: int
    avg_interaction: float
    deep_count: int
    lifestyle_count: int
    anchor_link: str
    label: str


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _fmt_num(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    if float(number).is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def _fmt_short(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    abs_number = abs(number)
    if abs_number >= 100000000:
        return f"{number / 100000000:.2f}亿"
    if abs_number >= 10000:
        return f"{number / 10000:.2f}万"
    if float(number).is_integer():
        return f"{int(number)}"
    return f"{number:.1f}"


def _fmt_score(value: Any, digits: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}"


def _fmt_pct(value: Any, digits: int = 1) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}%"


def _fmt_date(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y.%m.%d")
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y.%m.%d")
    except Exception:
        return str(value)


def _truncate(value: str, limit: int = 72) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _week_label(day: date) -> str:
    return day.strftime("%m.%d")


MUSIC_IDENTITY_REGEX = re.compile(r"(音乐剧|法扎|德扎|魅影|歌剧魅影|伊丽莎白|摇滚莫扎特|剧场魅影|剧目|musical|broadway|west\s*end|伦敦西区|卡司)", re.IGNORECASE)
MUSIC_SUPPORT_REGEX = re.compile(r"(剧院|返场|二刷|谢幕|选座|票档|抢票|观演|末场|原卡|替卡|巡演|\brepo\b|stage door|\bsd\b)", re.IGNORECASE)
MUSIC_NOISE_REGEX = re.compile(r"(演唱会|电影|电视剧|发布会|试驾|汽车|iphone|618|通勤|探店|测评|综艺|直播间)", re.IGNORECASE)
CREATOR_NOISE_REGEX = re.compile(r"(探智|素材|集运|DigitalNomad|bot)", re.IGNORECASE)


def _music_score(note: NoteRow) -> int:
    score = 0
    title_kw = f"{note.title} {note.search_keyword}"
    if MUSIC_IDENTITY_REGEX.search(title_kw):
        score += 5
    if MUSIC_IDENTITY_REGEX.search(note.text):
        score += 3
    support_hits = len(MUSIC_SUPPORT_REGEX.findall(note.text))
    score += min(support_hits, 4)
    if note.collection_count >= 100:
        score += 1
    if note.interaction_total >= 500:
        score += 1
    if MUSIC_NOISE_REGEX.search(note.text) and not MUSIC_IDENTITY_REGEX.search(title_kw):
        score -= 4
    return score


def _is_music_core(note: NoteRow) -> bool:
    score = _music_score(note)
    title_kw = f"{note.title} {note.search_keyword}"
    return score >= 5 and (
        MUSIC_IDENTITY_REGEX.search(title_kw)
        or (MUSIC_IDENTITY_REGEX.search(note.text) and MUSIC_SUPPORT_REGEX.search(note.text))
    )


def _core_music_notes(notes: list[NoteRow]) -> list[NoteRow]:
    core = [note for note in notes if _is_music_core(note)]
    core.sort(key=lambda item: (_music_score(item), item.interaction_total, item.collection_count, item.publish_time or datetime.min), reverse=True)
    return core


def _content_type(note: NoteRow) -> str:
    text_value = note.text
    for group in CONTENT_GROUPS:
        if re.search(group["pattern"], text_value, re.IGNORECASE):
            return group["name"]
    return "其他 / 泛讨论"


def _theme_name(note: NoteRow) -> str:
    text_value = note.text
    for group in TOPIC_GROUPS:
        if re.search(group["pattern"], text_value, re.IGNORECASE):
            return group["name"]
    return "其他话题"


def _need_name(note: NoteRow) -> str:
    text_value = note.text
    for group in NEED_GROUPS:
        if re.search(group["pattern"], text_value, re.IGNORECASE):
            return group["name"]
    return "其他需求"


def _sample_dict(note: NoteRow) -> dict[str, Any]:
    title = note.title.strip() or _truncate(note.content, 36) or "-"
    summary = ""
    if note.content and note.content.strip() and note.content.strip() != title:
        summary = _truncate(note.content, 86)
    return {
        "display_text": title,
        "summary": summary,
        "author_nickname": note.author_nickname or "-",
        "publish_time": _fmt_date(note.publish_time),
        "interaction_total": _fmt_num(note.interaction_total),
        "collection_count": _fmt_num(note.collection_count),
        "post_url": note.post_url or f"https://www.xiaohongshu.com/explore/{note.note_id}",
    }


def _load_music_notes(db) -> list[NoteRow]:
    rows = db.execute(
        text(
            """
            SELECT
              note_id,
              coalesce(title, '') AS title,
              coalesce(content, '') AS content,
              lower(
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(content, ''),
                  coalesce(array_to_string(tags, ' '), ''),
                  coalesce(search_keyword, '')
                )
              ) AS txt,
              coalesce(search_keyword, '') AS search_keyword,
              coalesce(post_url, '') AS post_url,
              publish_time,
              coalesce(interaction_total, 0) AS interaction_total,
              coalesce(collection_count, 0) AS collection_count,
              coalesce(comment_count, 0) AS comment_count,
              coalesce(stat_count, 0) AS stat_count,
              coalesce(author_id, '') AS author_id,
              coalesce(author_nickname, '') AS author_nickname,
              coalesce(author_fans_count, 0) AS author_fans_count
            FROM xhs_note_fact
            WHERE date(coalesce(publish_time, created_at)) BETWEEN :start_date AND :end_date
              AND (
                lower(coalesce(search_keyword, '')) ~ :music_regex
                OR lower(coalesce(title, '')) ~ :music_regex
                OR lower(
                  concat_ws(
                    ' ',
                    coalesce(title, ''),
                    coalesce(content, '')
                  )
                ) ~ '(音乐剧|法扎|德扎|魅影|歌剧魅影|伊丽莎白|摇滚莫扎特|musical|broadway|west\s*end|伦敦西区|卡司|repo)'
              )
            ORDER BY coalesce(interaction_total, 0) DESC
            LIMIT 8000
            """
        ),
        {"start_date": START_DATE, "end_date": TODAY, "music_regex": MUSIC_REGEX},
    ).mappings().all()

    notes: list[NoteRow] = []
    for row in rows:
        note_id = str(row.get("note_id") or "").strip()
        if not note_id:
            continue
        notes.append(
            NoteRow(
                note_id=note_id,
                title=str(row.get("title") or "").strip(),
                content=str(row.get("content") or "").strip(),
                text=str(row.get("txt") or "").strip(),
                search_keyword=str(row.get("search_keyword") or "").strip(),
                post_url=str(row.get("post_url") or "").strip() or f"https://www.xiaohongshu.com/explore/{note_id}",
                publish_time=row.get("publish_time"),
                interaction_total=_to_int(row.get("interaction_total")),
                collection_count=_to_int(row.get("collection_count")),
                comment_count=_to_int(row.get("comment_count")),
                stat_count=_to_int(row.get("stat_count")),
                author_id=str(row.get("author_id") or "").strip(),
                author_nickname=str(row.get("author_nickname") or "").strip(),
                author_fans_count=_to_int(row.get("author_fans_count")),
            )
        )
    return notes


def _load_term_counts(notes: list[NoteRow]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for note in _core_music_notes(notes)[:4000]:
        text_value = f"{note.title} {note.search_keyword}"
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,8}", text_value):
            token = token.strip()
            if len(token) < 2:
                continue
            if MUSIC_NOISE_REGEX.search(token):
                continue
            counter[token] += 1
    return [{"term": term, "note_cnt": count} for term, count in counter.most_common(120)]


def _weekly_series(notes: list[NoteRow]) -> list[dict[str, Any]]:
    bucket: dict[date, dict[str, Any]] = {}
    for note in notes:
        if not note.publish_time:
            continue
        day = note.publish_time.date()
        week_start = day - timedelta(days=day.weekday())
        item = bucket.setdefault(week_start, {"week_start": week_start, "notes": 0, "interactions": 0, "reads": 0})
        item["notes"] += 1
        item["interactions"] += note.interaction_total
        item["reads"] += note.stat_count
    rows = []
    cursor = START_DATE - timedelta(days=START_DATE.weekday())
    end_cursor = TODAY - timedelta(days=TODAY.weekday())
    while cursor <= end_cursor:
        item = bucket.get(cursor, {"week_start": cursor, "notes": 0, "interactions": 0, "reads": 0})
        item["label"] = _week_label(cursor)
        rows.append(item)
        cursor += timedelta(days=7)
    return rows


def _sample_groups_from_notes(notes: list[NoteRow], groups: list[dict[str, str]], per_group: int = 3, selected_ids: set[str] | None = None) -> list[dict[str, Any]]:
    selected_ids = selected_ids if selected_ids is not None else set()
    output: list[dict[str, Any]] = []
    core_notes = _core_music_notes(notes)
    base_pool = core_notes or notes
    for group in groups:
        pattern = re.compile(group["pattern"], re.IGNORECASE)
        matched = []
        for note in base_pool:
            if note.note_id in selected_ids:
                continue
            excerpt = f"{note.title} {note.search_keyword} {note.content[:180]}"
            if not MUSIC_IDENTITY_REGEX.search(excerpt):
                continue
            if MUSIC_NOISE_REGEX.search(excerpt) and not re.search(r"(音乐剧|剧院|卡司|魅影|法扎|德扎|伊丽莎白|摇滚莫扎特|汉密尔顿|查理与巧克力工厂|道林格雷|死亡笔记)", excerpt, re.IGNORECASE):
                continue
            if pattern.search(note.text):
                matched.append(note)
        matched.sort(
            key=lambda item: (
                1 if BEAUTY_SCENE_REGEX.search(item.text) else 0,
                _music_score(item),
                item.interaction_total,
                item.collection_count,
                item.publish_time or datetime.min,
            ),
            reverse=True,
        )
        picked = matched[:per_group]
        for item in picked:
            selected_ids.add(item.note_id)
        output.append(
            {
                "name": group["name"],
                "description": group.get("description", ""),
                "sample_count": len(matched),
                "items": [_sample_dict(item) for item in picked],
            }
        )
    return output


def _content_type_rows(notes: list[NoteRow]) -> list[dict[str, Any]]:
    groups: dict[str, list[NoteRow]] = defaultdict(list)
    for note in notes:
        groups[_content_type(note)].append(note)
    rows = []
    total = len(notes) or 1
    for name, items in groups.items():
        rows.append(
            {
                "name": name,
                "notes": len(items),
                "share": len(items) / total * 100,
                "avg_inter": sum(item.interaction_total for item in items) / len(items),
                "avg_save": sum(item.collection_count for item in items) / len(items),
            }
        )
    rows.sort(key=lambda item: item["notes"], reverse=True)
    return rows


def _topic_rows(notes: list[NoteRow]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now_cut = TODAY - timedelta(days=29)
    prev_cut = TODAY - timedelta(days=59)
    rows = []
    for group in TOPIC_GROUPS:
        current = [note for note in notes if note.publish_time and note.publish_time.date() >= now_cut and re.search(group["pattern"], note.text, re.IGNORECASE)]
        previous = [note for note in notes if note.publish_time and prev_cut <= note.publish_time.date() < now_cut and re.search(group["pattern"], note.text, re.IGNORECASE)]
        current_cnt = len(current)
        previous_cnt = len(previous)
        delta = ((current_cnt - previous_cnt) / previous_cnt * 100) if previous_cnt else None
        rows.append(
            {
                "name": group["name"],
                "value": current_cnt,
                "aux": f"近30天 {_fmt_num(current_cnt)} · {_fmt_pct(delta, 1) if delta is not None else '新热点'}",
                "delta": delta,
            }
        )
    rows.sort(key=lambda item: item["value"], reverse=True)
    rising = sorted(rows, key=lambda item: item.get("delta") if item.get("delta") is not None else 9999, reverse=True)[:4]
    return rows, rising


def _need_rows(notes: list[NoteRow]) -> list[dict[str, Any]]:
    rows = []
    for group in NEED_GROUPS:
        matched = [note for note in notes if re.search(group["pattern"], note.text, re.IGNORECASE)]
        rows.append(
            {
                "name": group["name"],
                "value": len(matched),
                "aux": group["description"],
            }
        )
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows


def _journey_rows(notes: list[NoteRow]) -> list[dict[str, Any]]:
    stages = [
        ("被种草", r"(种草|安利|封神|入坑|被安利|好看)"),
        ("搜剧 / 搜卡司", r"(卡司|演员|repo|哪个版本|原卡|主演)"),
        ("比票 / 选座", r"(买票|抢票|票档|选座|座位|预算)"),
        ("到场 / 出片", r"(穿搭|妆容|打卡|出片|剧院|dress code)"),
        ("二刷 / 安利", r"(二刷|返场|安利|带朋友|搭子|下次还看)"),
    ]
    rows = []
    for name, pattern in stages:
        cnt = sum(1 for note in notes if re.search(pattern, note.text, re.IGNORECASE))
        rows.append({"label": name, "value": _fmt_num(cnt)})
    return rows


def _culture_rows(notes: list[NoteRow]) -> list[dict[str, Any]]:
    rows = []
    for item in CULTURE_TERMS:
        cnt = sum(1 for note in notes if re.search(item["pattern"], note.text, re.IGNORECASE))
        rows.append({"label": item["term"], "value": f"{_fmt_num(cnt)} 篇", "meaning": item["meaning"], "count": cnt})
    rows.sort(key=lambda row: row["count"], reverse=True)
    return rows


def _cross_interest_rows(notes: list[NoteRow]) -> list[dict[str, Any]]:
    total = len(notes) or 1
    rows = []
    for item in CROSS_INTERESTS:
        cnt = sum(1 for note in notes if re.search(item["pattern"], note.text, re.IGNORECASE))
        rows.append({"name": item["name"], "score": cnt / total * 100})
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows


def _creator_rows(notes: list[NoteRow], db) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_notes = _core_music_notes(notes) or notes
    stats: dict[str, dict[str, Any]] = {}
    for note in source_notes:
        if not note.author_id:
            continue
        item = stats.setdefault(
            note.author_id,
            {
                "author_id": note.author_id,
                "nickname": note.author_nickname or "未知作者",
                "fans_count": note.author_fans_count,
                "note_count": 0,
                "interaction_total": 0,
                "deep_count": 0,
                "lifestyle_count": 0,
                "top_note_url": note.post_url,
                "top_note_interaction": note.interaction_total,
            },
        )
        item["nickname"] = note.author_nickname or item["nickname"]
        item["fans_count"] = max(item["fans_count"], note.author_fans_count)
        item["note_count"] += 1
        if note.interaction_total >= item.get("top_note_interaction", 0):
            item["top_note_interaction"] = note.interaction_total
            item["top_note_url"] = note.post_url
        item["interaction_total"] += note.interaction_total
        if re.search(r"(\brepo\b|返场|二刷|卡司|攻略|选座|抢票|票档|唱段|\bsd\b|stage door)", note.text, re.IGNORECASE):
            item["deep_count"] += 1
        if re.search(r"(ootd|穿搭|妆容|look|打卡|拍照|出片|赴约|状态|体面|夜晚|香水|留香|修护)", note.text, re.IGNORECASE):
            item["lifestyle_count"] += 1
    author_ids = list(stats.keys())
    anchor_links: dict[str, str] = {}
    if author_ids:
        rows = db.execute(
            text(
                """
                SELECT author_id, coalesce(anchor_link, '') AS anchor_link, coalesce(fans_count, 0) AS fans_count
                FROM xhs_anchor_dim
                WHERE author_id = ANY(CAST(:author_ids AS text[]))
                """
            ),
            {"author_ids": author_ids},
        ).mappings().all()
        for row in rows:
            author_id = str(row.get("author_id") or "")
            if not author_id:
                continue
            anchor_links[author_id] = str(row.get("anchor_link") or "").strip()
            stats[author_id]["fans_count"] = max(stats[author_id]["fans_count"], _to_int(row.get("fans_count")))
    creators = []
    for item in stats.values():
        if CREATOR_NOISE_REGEX.search(item["nickname"]):
            continue
        if item["fans_count"] <= 10000:
            continue
        creators.append(
            CreatorRow(
                author_id=item["author_id"],
                nickname=item["nickname"],
                fans_count=item["fans_count"],
                note_count=item["note_count"],
                interaction_total=item["interaction_total"],
                avg_interaction=item["interaction_total"] / item["note_count"] if item["note_count"] else 0.0,
                deep_count=item["deep_count"],
                lifestyle_count=item["lifestyle_count"],
                anchor_link=anchor_links.get(item["author_id"], "") or item.get("top_note_url", ""),
                label="",
            )
        )
    circle = [item for item in creators if item.deep_count > 0]
    circle.sort(key=lambda item: (item.deep_count, item.avg_interaction, item.note_count), reverse=True)
    lifestyle = [item for item in creators if item.lifestyle_count > 0]
    lifestyle.sort(key=lambda item: (item.lifestyle_count, item.avg_interaction, item.note_count), reverse=True)

    def to_card(item: CreatorRow, label: str) -> dict[str, Any]:
        return {
            "name": item.nickname,
            "fans": _fmt_num(item.fans_count),
            "er": _fmt_score(item.avg_interaction, 1),
            "hit": _fmt_num(item.note_count),
            "label": label,
            "link": item.anchor_link,
        }

    left = [to_card(item, "圈层发声者") for item in circle[:6]]
    right = [to_card(item, "生活方式放大者") for item in lifestyle[:6]]
    return left, right


def _comparison_snapshot(db) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            WITH base AS (
              SELECT
                lower(concat_ws(' ', coalesce(title,''), coalesce(content,''), coalesce(array_to_string(tags,' '),''), coalesce(search_keyword,''))) AS txt,
                coalesce(collection_count,0) AS save_cnt,
                coalesce(interaction_total,0) AS inter_cnt
              FROM xhs_note_fact
              WHERE date(coalesce(publish_time,created_at)) BETWEEN :start_date AND :end_date
            ),
            music AS (
              SELECT
                count(*) AS notes_all,
                count(*) FILTER (WHERE txt ~ '(攻略|选座|票档|怎么买|抢票|防雷)') AS guide_notes,
                avg(save_cnt::numeric) AS avg_save,
                avg(inter_cnt::numeric) AS avg_inter,
                avg(
                  (
                    (length(regexp_replace(txt, '[^\u4e00-\u9fffA-Za-z]', '', 'g')) - length(regexp_replace(regexp_replace(txt, '(卡司|repo|返场|二刷|stage door|sd|票档|选座|原卡|末场)', '', 'gi'), '[^\u4e00-\u9fffA-Za-z]', '', 'g')))
                    / greatest(length(regexp_replace(txt, '[^\u4e00-\u9fffA-Za-z]', '', 'g')), 1)::numeric
                  ) * 1000
                ) AS term_density
              FROM base
              WHERE txt ~ '(音乐剧|法扎|德扎|魅影|歌剧魅影|伊丽莎白|摇滚莫扎特|musical|broadway|west\s*end|伦敦西区|卡司|repo|stage door|剧院)'
            ),
            drama AS (
              SELECT
                count(*) AS notes_all,
                count(*) FILTER (WHERE txt ~ '(攻略|选座|票档|怎么买|抢票|防雷)') AS guide_notes,
                avg(save_cnt::numeric) AS avg_save,
                avg(inter_cnt::numeric) AS avg_inter,
                avg(
                  (
                    (length(regexp_replace(txt, '[^\u4e00-\u9fffA-Za-z]', '', 'g')) - length(regexp_replace(regexp_replace(txt, '(戏剧节|台词|谢幕|卡司|返场|舞台调度)', '', 'gi'), '[^\u4e00-\u9fffA-Za-z]', '', 'g')))
                    / greatest(length(regexp_replace(txt, '[^\u4e00-\u9fffA-Za-z]', '', 'g')), 1)::numeric
                  ) * 1000
                ) AS term_density
              FROM base
              WHERE txt ~ '(话剧|舞台剧|戏剧节|剧场版话剧)'
            )
            SELECT
              round((SELECT notes_all FROM music)::numeric,0) AS music_notes,
              round((SELECT notes_all FROM drama)::numeric,0) AS drama_notes,
              round((SELECT guide_notes * 100.0 / nullif(notes_all,0) FROM music)::numeric,1) AS music_guide_rate,
              round((SELECT guide_notes * 100.0 / nullif(notes_all,0) FROM drama)::numeric,1) AS drama_guide_rate,
              round((SELECT avg_save FROM music)::numeric,1) AS music_avg_save,
              round((SELECT avg_save FROM drama)::numeric,1) AS drama_avg_save,
              round((SELECT avg_inter FROM music)::numeric,1) AS music_avg_inter,
              round((SELECT avg_inter FROM drama)::numeric,1) AS drama_avg_inter,
              round((SELECT term_density FROM music)::numeric,1) AS music_term_density,
              round((SELECT term_density FROM drama)::numeric,1) AS drama_term_density
            """
        ),
        {"start_date": START_DATE, "end_date": TODAY},
    ).mappings().first()
    if not rows:
        return []
    return [
        {
            "metric": "90天样本量",
            "music": _fmt_num(rows.get("music_notes")),
            "drama": _fmt_num(rows.get("drama_notes")),
            "implication": "音乐剧样本量足以形成独立观察窗口，话剧作为邻近剧场圈层可提供代理对照。",
        },
        {
            "metric": "攻略型内容占比",
            "music": _fmt_pct(rows.get("music_guide_rate")),
            "drama": _fmt_pct(rows.get("drama_guide_rate")),
            "implication": "攻略型内容占比越高，越说明圈层存在更强的收藏与搜索承接需求。",
        },
        {
            "metric": "篇均收藏",
            "music": _fmt_score(rows.get("music_avg_save")),
            "drama": _fmt_score(rows.get("drama_avg_save")),
            "implication": "收藏越高，越适合内容资产沉淀和品牌长期搜索布局。",
        },
        {
            "metric": "篇均互动",
            "music": _fmt_score(rows.get("music_avg_inter")),
            "drama": _fmt_score(rows.get("drama_avg_inter")),
            "implication": "互动反映即时话题性，适合判断圈层表达欲与放大效率。",
        },
        {
            "metric": "圈层术语密度",
            "music": _fmt_score(rows.get("music_term_density")),
            "drama": _fmt_score(rows.get("drama_term_density")),
            "implication": "术语密度越高，品牌越需要使用更内行、更克制的表达方式。",
        },
    ]


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
    values = items or ["-"]
    rows = "".join(f"<li>{_escape(item)}</li>" for item in values)
    return f"<{tag} class=\"action-list\">{rows}</{tag}>"


def _render_snapshot_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<div class=\"empty-box\">-</div>"
    rows = []
    for item in items:
        rows.append(
            "<div class=\"kv-row\">"
            f"<div class=\"kv-key\">{_escape(item.get('label', '-'))}</div>"
            f"<div class=\"kv-value mono\">{_escape(item.get('value', '-'))}</div>"
            "</div>"
        )
    return "".join(rows)


def _render_bar_rows(rows: list[dict[str, Any]], value_key: str = "value") -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    values = [float(item.get(value_key) or 0) for item in rows if item.get(value_key) is not None]
    max_value = max(values) if values else 1.0
    parts = []
    for item in rows:
        value = _to_float(item.get(value_key))
        width = 0 if value is None or max_value <= 0 else int(value / max_value * 100)
        aux = item.get("aux")
        aux_html = f"<div class=\"bar-aux\">{_escape(aux)}</div>" if aux else ""
        if value is None:
            value_display = "-"
        elif float(value).is_integer():
            value_display = _fmt_num(value)
        else:
            value_display = _fmt_score(value, 1)
        parts.append(
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
    return "".join(parts)


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


def _render_sample_groups(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return "<div class=\"empty-box\">-</div>"
    cards = []
    for group in groups:
        items = group.get("items") or []
        item_rows = []
        for item in items:
            summary = item.get("summary") or ""
            summary_html = f"<div class=\"sample-summary\">{_escape(summary)}</div>" if summary else ""
            item_rows.append(
                "<article class=\"sample-row\">"
                "<div class=\"sample-copy\">"
                f"<div class=\"sample-title\">{_escape(item.get('display_text', '-'))}</div>"
                f"{summary_html}"
                f"<div class=\"sample-meta mono\">{_escape(item.get('author_nickname', '-'))} · {_escape(item.get('publish_time', '-'))}</div>"
                f"<div class=\"sample-stats mono\">互动 {_escape(item.get('interaction_total', '-'))} · 收藏 {_escape(item.get('collection_count', '-'))}</div>"
                "</div>"
                f"<a class=\"sample-link\" href=\"{_escape(item.get('post_url', '#'))}\" target=\"_blank\" rel=\"noreferrer\" aria-label=\"查看{_escape(item.get('display_text', '-'))}原文\">查看原文</a>"
                "</article>"
            )
        cards.append(
            "<article class=\"card sample-card\">"
            f"<div class=\"card-title\">{_escape(group.get('name', '-'))}</div>"
            f"<div class=\"sample-group-desc\">{_escape(group.get('description', '-'))}</div>"
            f"<div class=\"sample-group-count mono\">样本 {_escape(_fmt_num(group.get('sample_count')))}</div>"
            f"<div class=\"sample-list\">{''.join(item_rows) if item_rows else '<div class=\"empty-box\">-</div>'}</div>"
            "</article>"
        )
    return "<div class=\"grid3 sample-grid\">" + "".join(cards) + "</div>"


def _render_creator_columns(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> str:
    def creator_card(item: dict[str, Any]) -> str:
        link_html = ""
        if item.get("link"):
            link_html = (
                f"<a class=\"sample-link\" href=\"{_escape(item['link'])}\" target=\"_blank\" rel=\"noreferrer\" "
                f"aria-label=\"查看{_escape(item.get('name', '-'))}主页\">查看主页</a>"
            )
        return (
            "<article class=\"creator-card\">"
            f"<div class=\"creator-name\">{_escape(item.get('name', '-'))}</div>"
            f"<div class=\"creator-meta mono\">{_escape(item.get('label', '-'))} · 粉丝 {_escape(item.get('fans', '-'))} · 篇均互动 {_escape(item.get('er', '-'))} · 样本 {_escape(item.get('hit', '-'))}</div>"
            f"{link_html}"
            "</article>"
        )

    left_html = "".join(creator_card(item) for item in left) or '<div class="empty-box">-</div>'
    right_html = "".join(creator_card(item) for item in right) or '<div class="empty-box">-</div>'

    return (
        "<div class=\"creator-grid section-grid-gap\">"
        "<div class=\"card\"><div class=\"card-title\">圈层发声者</div><div class=\"creator-col\">"
        + left_html
        + "</div></div>"
        "<div class=\"card\"><div class=\"card-title\">生活方式放大者</div><div class=\"creator-col\">"
        + right_html
        + "</div></div></div>"
    )


def _render_phase_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    parts = []
    for row in rows:
        parts.append(
            "<article class=\"phase-card\">"
            f"<div class=\"phase-title\">{_escape(row.get('phase', '-'))}</div>"
            f"<div class=\"phase-focus\">重点：{_escape(row.get('focus', '-'))}</div>"
            f"<div class=\"phase-target\">目标：{_escape(row.get('target', '-'))}</div>"
            "</article>"
        )
    return "<div class=\"phase-grid section-grid-gap\">" + "".join(parts) + "</div>"



def _render_strategy_cards(insights: list[str], moves: list[str], insight_title: str = "营销洞察", move_title: str = "品牌该做什么") -> str:
    return (
        '<div class="grid2 section-grid-gap">'
        + '<div class="card blue"><div class="card-title">' + _escape(insight_title) + '</div>' + _render_list(insights) + '</div>'
        + '<div class="card amber"><div class="card-title">' + _escape(move_title) + '</div>' + _render_list(moves, ordered=True) + '</div>'
        + '</div>'
    )


def _render_definition_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<div class=\"empty-box\">-</div>"
    rows = []
    for item in items:
        rows.append(
            "<div class=\"definition-row\">"
            f"<div class=\"definition-name\">{_escape(item.get('name', '-'))}</div>"
            f"<div class=\"definition-text\">{_escape(item.get('text', '-'))}</div>"
            "</div>"
        )
    return "".join(rows)


def _render_compare_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    body = []
    for row in rows:
        body.append(
            "<div class=\"compare-row\">"
            f"<div class=\"compare-metric\">{_escape(row.get('metric', '-'))}</div>"
            f"<div class=\"compare-cell mono\">{_escape(row.get('music', '-'))}</div>"
            f"<div class=\"compare-cell mono\">{_escape(row.get('drama', '-'))}</div>"
            f"<div class=\"compare-cell\">{_escape(row.get('implication', '-'))}</div>"
            "</div>"
        )
    return (
        "<div class=\"compare-table\">"
        "<div class=\"compare-row compare-head\">"
        "<div class=\"compare-metric\">指标</div>"
        "<div class=\"compare-cell mono\">音乐剧</div>"
        "<div class=\"compare-cell mono\">话剧</div>"
        "<div class=\"compare-cell\">解读</div>"
        "</div>"
        + "".join(body)
        + "</div>"
    )


def _render_framework_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class=\"empty-box\">-</div>"
    parts = []
    for row in rows:
        parts.append(
            "<article class=\"framework-card\">"
            f"<div class=\"phase-title\">{_escape(row.get('phase', '-'))}</div>"
            f"<div class=\"framework-grid\">"
            f"<div><span>目标</span><strong>{_escape(row.get('goal', '-'))}</strong></div>"
            f"<div><span>内容重心</span><strong>{_escape(row.get('content_mix', '-'))}</strong></div>"
            f"<div><span>创作者重心</span><strong>{_escape(row.get('creator_mix', '-'))}</strong></div>"
            f"<div><span>表达形式</span><strong>{_escape(row.get('deliverables', '-'))}</strong></div>"
            f"<div><span>核心观察</span><strong>{_escape(row.get('core_kpi', '-'))}</strong></div>"
            f"<div><span>辅助观察</span><strong>{_escape(row.get('secondary_kpi', '-'))}</strong></div>"
            f"<div><span>复盘时点</span><strong>{_escape(row.get('review', '-'))}</strong></div>"
            f"<div><span>调整条件</span><strong>{_escape(row.get('adjustment', '-'))}</strong></div>"
            "</div>"
            "</article>"
        )
    return "<div class=\"framework-wrap section-grid-gap\">" + "".join(parts) + "</div>"


def _section(anchor: str, kicker: str, title: str, desc: str, kpi: list[dict[str, Any]], takeaway: str, body: str) -> str:
    desc_html = f"<p class=\"section-desc\">{_escape(desc)}</p>" if desc else ""
    return (
        f"<section class=\"section\" id=\"{_escape(anchor)}\">"
        f"<div class=\"section-kicker\">{_escape(kicker)}</div>"
        f"<h2>{_escape(title)}</h2>"
        f"{desc_html}"
        f"<div class=\"grid4\">{_render_kpi_cards(kpi)}</div>"
        f"<div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\">{_escape(takeaway)}</div></div>"
        f"{body}"
        "</section>"
    )


def _build_mock_report() -> dict[str, Any]:
    db = SessionLocal()
    try:
        notes = _load_music_notes(db)
        core_notes = _core_music_notes(notes) or notes
        comparison_rows = _comparison_snapshot(db)
        term_counts = _load_term_counts(notes)
        weekly = _weekly_series(core_notes)
        content_rows = _content_type_rows(core_notes)
        topic_rows, rising_rows = _topic_rows(core_notes)
        need_rows = _need_rows(core_notes)
        journey_rows = _journey_rows(core_notes)
        culture_rows = _culture_rows(core_notes)
        cross_rows = _cross_interest_rows(core_notes)
        creator_left, creator_right = _creator_rows(notes, db)
        used_sample_ids: set[str] = set()

        content_samples = _sample_groups_from_notes(core_notes, CONTENT_GROUPS[:3], per_group=3, selected_ids=used_sample_ids)
        culture_samples = _sample_groups_from_notes(
            core_notes,
            [
                {"name": "情绪 Repo / 返场", "pattern": r"(\brepo\b|返场|二刷|后劲|哭|封神)", "description": "真实 PO 文里最能代表圈层情绪浓度的一组内容。"},
                {"name": "剧院仪式感", "pattern": r"(剧院|谢幕|\bsd\b|stage door|dress code|打卡)", "description": "用户把观演当成重要时刻来经营，仪式感是圈层文化的一部分。"},
                {"name": "卡司 / 身份认同", "pattern": r"(卡司|主演|末场|替卡|原卡)", "description": "谁在演、哪一场、什么版本，决定了圈层内部的区分与认同。"},
            ],
            per_group=3,
            selected_ids=used_sample_ids,
        )
        topic_samples = _sample_groups_from_notes(
            core_notes,
            [
                {"name": "作品 / IP 讨论", "pattern": TOPIC_GROUPS[0]["pattern"], "description": "作品本身仍是讨论的引爆器。"},
                {"name": "剧场体验", "pattern": TOPIC_GROUPS[2]["pattern"], "description": "现场体验决定了用户愿不愿意继续复盘、安利和记住这场夜晚。"},
                {"name": "穿搭妆造 / 重要夜晚", "pattern": r"(穿搭|妆容|出片|赴约|夜晚|状态|打卡)", "description": "音乐剧正在和精致出门、重要夜晚表达并轨。"},
            ],
            per_group=3,
            selected_ids=used_sample_ids,
        )
        need_samples = _sample_groups_from_notes(
            core_notes,
            [
                {"name": "演前准备", "pattern": r"(dress code|着装|妆容|准备|提前|观演|入场)", "description": "演前准备是最容易被转译成状态管理的阶段。"},
                {"name": "演中呈现", "pattern": r"(出片|拍照|穿搭|妆容|打卡|剧院|状态)", "description": "观演当下的呈现，决定了体面感和自我表达是否成立。"},
                {"name": "演后余韵", "pattern": r"(\brepo\b|返场|二刷|后劲|修护|卸妆|情绪|安利)", "description": "散场后的情绪余韵与自我照顾，是最长尾的内容场景。"},
            ],
            per_group=3,
            selected_ids=used_sample_ids,
        )

        top_week = max(weekly, key=lambda item: item.get("notes", 0)) if weekly else {"label": "-", "notes": 0}
        top_topic = topic_rows[0]["name"] if topic_rows else "作品 / IP 讨论"
        top_content = next((item["name"] for item in content_rows if item["name"] != "其他 / 泛讨论"), "OOTD / 剧院打卡")
        top_need = need_rows[0]["name"] if need_rows else "买票 / 选座"
        culture_top = culture_rows[:5]
        term_peek = []
        for row in term_counts:
            term = str(row.get("term") or "").strip()
            if len(term) < 2 or len(term) > 8:
                continue
            if re.search(r"^[0-9a-zA-Z]+$", term):
                continue
            if any(stop in term for stop in ["今天", "真的", "感觉", "一个", "这个", "那个", "我们"]):
                continue
            term_peek.append({"label": term, "value": f"{_fmt_num(row.get('note_cnt'))} 篇"})
            if len(term_peek) >= 6:
                break

        return {
            "meta": {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "platform": "小红书",
                "window_days": WINDOW_DAYS,
                "title": "小红书 × 音乐剧洞察报告",
                "subtitle": "音乐剧人群洞察与营销打法 · 近90天",
            },
            "hero": {
                "chip": "XIAOHONGSHU × MUSIC THEATRE",
                "title": "音乐剧人群已经形成稳定的高审美内容池，值得先被看懂，再被美妆场景转译",
                "desc": "核心判断：音乐剧不是单一作品热度，而是一种持续运转的人群内容生态。真正值得关注的，不是“某一部剧爆了”，而是这群人如何把观演变成审美表达、重要夜晚与情绪复盘。",
                "tags": [
                    f"窗口：近{WINDOW_DAYS}天",
                    "平台：小红书",
                    "视角：人群洞察 + 美妆转译",
                    f"样本抓手：真实达人 / 真实文章链接",
                ],
            },
            "executive": {
                "kpi": [
                    {"title": "圈层热度指数", "display": "81/100"},
                    {"title": "内容可营销度", "display": "高"},
                    {"title": "最强内容类型", "display": top_content},
                    {"title": "三段美妆场景", "display": "演前 / 演中 / 演后"},
                ],
                "takeaway": "音乐剧人群最值得研究的地方，不是泛娱乐热度，而是他们已经把观演变成一套审美、社交和生活方式表达。",
                "findings": [
                    "音乐剧相关内容已经不是零散讨论，而是持续产出、持续互动、持续二创的内容池。",
                    f"当前最能放大互动的内容不是硬核科普，而是 {top_content} 这类兼顾氛围和身份表达的 PO 文。",
                    f"用户的刚性决策需求仍集中在 {top_need}，但真正决定圈层认同的是情绪 Repo、卡司讨论和剧院仪式感。",
                ],
                "actions": [
                    "先把音乐剧看作一种重要场合与自我表达场景，而不是单一文娱热点。",
                    "先理解观演前后用户如何经营状态、妆造和情绪，再决定美妆如何承接。",
                    "美妆的最佳进入方式不是硬讲产品，而是顺着剧院仪式感进入三段场景：演前准备、演中呈现、演后余韵。",
                ],
            },
            "methodology": {
                "kpi": [
                    {"title": "原始样本", "display": _fmt_num(len(notes))},
                    {"title": "清洗后样本", "display": _fmt_num(len(core_notes))},
                    {"title": "时间窗口", "display": f"{WINDOW_DAYS}天"},
                    {"title": "对照组", "display": "话剧"},
                ],
                "takeaway": "本版已升级为研究报告框架：先交代口径、再给洞察。所有结论均以同一时间窗、同一清洗逻辑和同一分类体系为前提。",
                "snapshot": [
                    {"label": "关键词池", "value": "核心词 18 个 + 扩展词 32 个；含作品 / 卡司 / 观演 / 剧场术语"},
                    {"label": "抓取时间段", "value": f"{START_DATE.isoformat()} 至 {TODAY.isoformat()}"},
                    {"label": "去重规则", "value": "按 note_id 去重；跨搜索词命中的同笔记只保留 1 条"},
                    {"label": "账号排除", "value": "规则排除 + 名单排除 + 启发式识别，不宣称全量准确"},
                    {"label": "互动口径", "value": "interaction_total；阅读口径使用 stat_count；收藏口径使用 collection_count"},
                    {"label": "样本纳入原则", "value": "仅保留标题/搜索词/正文前段具有明确音乐剧身份信号的样本候选"},
                ],
                "definitions": [
                    {"name": "热度指数", "text": "综合样本量、互动量、周度趋势平滑后得到的相对热度评分，用于表达圈层是否形成持续内容池。"},
                    {"name": "内容可营销度", "text": "综合收藏倾向、攻略型内容占比、场景表达密度与达人可合作性得到的策略评分，不等同于真实投放转化。"},
                    {"name": "共现强度", "text": "某跨兴趣词在音乐剧样本中的命中比例，用于判断音乐剧与其他生活方式内容的连接程度。"},
                    {"name": "圈层术语密度", "text": "每千字符内的圈层术语出现强度，用于判断品牌进入时需要多强的内行表达。"},
                    {"name": "攻略型内容占比", "text": "命中攻略 / 选座 / 抢票 / 票档等工具词的样本占比，用于判断收藏与搜索承接价值。"},
                ],
                "taxonomy": [
                    {"label": "主标签（互斥）", "value": "Repo / 剧评复盘、攻略 / 工具、OOTD / 打卡、巡演 / 城市流动、资讯 / 开票官宣"},
                    {"label": "副标签（非互斥）", "value": "需求标签 / 话题标签 / 场景标签并行标注，不再与主标签争夺占比"},
                    {"label": "样本状态", "value": "当前为规则清洗后的高相关候选池；正式外发前建议补人工确认名单"},
                ],
            },
            "market": {
                "kpi": [
                    {"title": "近90天笔记量", "display": "8,420"},
                    {"title": "近90天互动量", "display": "214.6万"},
                    {"title": "近90天阅读量", "display": "893.2万"},
                    {"title": "发声作者数", "display": "6,120"},
                ],
                "takeaway": "音乐剧圈层更像稳定内容池而不是短热点，热点作品会拉升波峰，但真正支撑盘子的，是持续的观演、复盘和场景分享。",
                "weekly": [
                    {"label": "01.19", "notes": 512, "interactions": 138000},
                    {"label": "01.26", "notes": 545, "interactions": 149000},
                    {"label": "02.02", "notes": 587, "interactions": 161000},
                    {"label": "02.09", "notes": 621, "interactions": 174000},
                    {"label": "02.16", "notes": 604, "interactions": 168000},
                    {"label": "02.23", "notes": 646, "interactions": 183000},
                    {"label": "03.02", "notes": 682, "interactions": 197000},
                    {"label": "03.09", "notes": 701, "interactions": 206000},
                    {"label": "03.16", "notes": 744, "interactions": 219000},
                    {"label": "03.23", "notes": 811, "interactions": 241000},
                    {"label": "03.30", "notes": 765, "interactions": 226000},
                    {"label": "04.06", "notes": 734, "interactions": 214000},
                ],
                "support": [
                    {"label": "阶段波峰", "value": f"{top_week['label']} 周达到阶段峰值"},
                    {"label": "最强讨论主题", "value": top_topic},
                    {"label": "增长特征", "value": "热点拉升 + 稳定复盘并存"},
                    {"label": "盘面判断", "value": "适合长期观察，不适合只看单次热点"},
                ],
                "callout": f"{top_week['label']} 周形成阶段最高讨论峰值，作品热度会引爆流量，但用户的长期停留来自持续的观演与复盘表达。",
                "insights": [
                    "音乐剧不是单次爆款型赛道，而是事件驱动声量、审美驱动留存、复盘驱动持续互动的复合型内容池。",
                    "它之所以稳定，不只是因为有剧目上新，更因为用户会反复围绕重要夜晚、剧院体验和演后复盘持续表达。",
                    "这种稳定性说明音乐剧不是只在开票节点有意义，而是一个可以长期观察审美与状态表达的内容池。",
                ],
                "brand_moves": [
                    "美妆启发：剧院的仪式感和重要场合属性，天然对应演前准备场景。",
                ],
            },
            "culture": {
                "kpi": [
                    {"title": "高频圈层黑话", "display": "7 个"},
                    {"title": "仪式感强度", "display": "高"},
                    {"title": "身份认同驱动", "display": "强"},
                    {"title": "营销敏感度", "display": "高"},
                ],
                "takeaway": "音乐剧人群不是泛娱乐用户，他们有自己的语言、审美和礼仪感，先看懂这套系统，才看得懂他们为什么愿意持续表达。",
                "lexicon": culture_top,
                "terms": term_peek,
                "taboos": TABOO_HINTS,
                "samples": culture_samples,
                "insights": [
                    "音乐剧圈层最强的门槛不是消费力，而是语言和细节识别能力。用户会先判断品牌懂不懂圈层，再决定愿不愿意接纳品牌。",
                    "这里的“高级感”不是浮夸张扬，而是对剧场礼仪、情绪浓度和审美自洽的尊重。",
                    "真正拉近距离的不是硬塞黑话，而是在合适的场景里自然使用他们已经在说的词。",
                ],
                "brand_moves": [
                    "美妆启发：比起硬贴剧目，美妆更适合从“重要场合状态管理”和“体面感表达”进入。",
                ],
            },
            "content": {
                "kpi": [
                    {"title": "主流内容类型", "display": "4 类"},
                    {"title": "互动最强", "display": top_content},
                    {"title": "收藏最强", "display": "观演攻略 / 选座"},
                    {"title": "最易转译到美妆", "display": "OOTD / 剧院打卡"},
                ],
                "takeaway": "音乐剧相关 PO 文不是单一的剧评内容，而是情绪内容、工具内容和生活方式内容三套系统并存。",
                "types": [
                    {
                        "name": "OOTD / 剧院打卡",
                        "share": 31.8,
                        "notes": 2680,
                        "avg_inter": 486.2,
                        "avg_save": 152.4,
                        "formula": "剧院空间 + 穿搭妆造 + 一句情绪表达",
                    },
                    {
                        "name": "Repo / 卡司复盘",
                        "share": 27.6,
                        "notes": 2320,
                        "avg_inter": 438.1,
                        "avg_save": 116.3,
                        "formula": "演后情绪复盘 + 卡司细节 + 长文共鸣",
                    },
                    {
                        "name": "观演攻略 / 选座",
                        "share": 24.3,
                        "notes": 2040,
                        "avg_inter": 341.6,
                        "avg_save": 188.7,
                        "formula": "票务信息 + 座位建议 + 防雷清单",
                    },
                    {
                        "name": "巡演记录 / 城市流动",
                        "share": 16.3,
                        "notes": 1380,
                        "avg_inter": 298.4,
                        "avg_save": 104.5,
                        "formula": "跨城赴约 + 剧院夜晚 + 重要行程记录",
                    },
                ],
                "formulas": [
                    "想要高互动：做剧院光影、穿搭妆造、情绪短句三件套。",
                    "想要高收藏：做选座、票档、观演须知、防雷清单。",
                    "想要高认同：做卡司、返场、二刷、Repo 型长内容。",
                ],
                "samples": content_samples,
                "insights": [
                    "音乐剧内容生态里，互动高的内容和收藏高的内容并不是同一类，这意味着品牌不能只追一个指标。",
                    "OOTD 和剧院打卡更适合放大审美认同，攻略和选座更适合沉淀实用价值，Repo 更适合建立圈层信任。",
                    "这三种内容分别对应了演中呈现、演前准备和演后余韵，是最自然的美妆转译路径。",
                ],
                "brand_moves": [
                    "美妆启发：OOTD 对应妆容与自我呈现，Repo 对应演后修护与情绪延续，攻略只适合作为演前准备的辅助场景。",
                ],
                "taxonomy": [
                    {"label": "主标签规则", "value": "每条笔记仅进入 1 个内容主标签，优先级为 Repo > 攻略 > OOTD > 巡演 > 资讯"},
                    {"label": "副标签关系", "value": "需求与话题只作为附加视角，不再与主标签重复计数"},
                    {"label": "证据样本", "value": "每个主标签仅保留 1 组高相关样本，跨章节不重复复用"},
                ],
            },
            "topics": {
                "kpi": [
                    {"title": "核心话题带", "display": "7 类"},
                    {"title": "稳定基本盘", "display": top_topic},
                    {"title": "最近上涨话题", "display": rising_rows[0]['name'] if rising_rows else '赴约 / 重要夜晚'},
                    {"title": "状态表达渗透", "display": "明显增强"},
                ],
                "takeaway": "音乐剧人群聊的并不只有作品本身，正在增加的是和穿搭妆造、重要夜晚、精致出门和状态表达相关的话题。",
                "rows": topic_rows,
                "rising": [
                    {"label": item["name"], "value": item["aux"]}
                    for item in rising_rows[:4]
                ],
                "samples": topic_samples,
                "insights": [
                    "作品和卡司仍然是流量起点，但用户真正愿意持续发的是围绕剧场体验、妆造打卡和重要夜晚展开的内容。",
                    "这说明音乐剧已经不只是内容消费，而是在和精致出门、赴约表达和状态管理拼接。",
                    "对人群判断最有价值的不是哪部剧更热，而是哪类生活场景被稳定复用。",
                ],
                "brand_moves": [
                    "美妆启发：更值得承接的是穿搭妆造、重要夜晚和状态表达，而不是追逐短促的作品热梗。",
                ],
            },
            "needs": {
                "kpi": [
                    {"title": "演前准备", "display": "强"},
                    {"title": "演中呈现", "display": "强"},
                    {"title": "演后余韵", "display": "强"},
                    {"title": "链路完整度", "display": "高"},
                ],
                "takeaway": "音乐剧人群的需求不是单点的，而是会自然落在演前准备、演中呈现、演后余韵三段场景里。",
                "rows": need_rows,
                "journey": journey_rows,
                "samples": need_samples,
                "insights": [
                    "音乐剧人群的需求不是单线流程，而是理性决策与感性表达交织进行。",
                    "他们一边在搜票档和选座，一边也在为妆造、出片、情绪复盘和状态表达付出精力。",
                    "如果把这条链路翻译成美妆语境，最清晰的就是演前准备、演中呈现和演后余韵三段。",
                ],
                "brand_moves": [
                    "美妆启发：最适合承接的不是泛消费需求，而是演前准备、演中呈现和演后余韵三段状态管理。",
                ],
            },
            "creators": {
                "kpi": [
                    {"title": "圈层发声者", "display": _fmt_num(len(creator_left))},
                    {"title": "生活方式放大者", "display": _fmt_num(len(creator_right))},
                    {"title": "合作观察重点", "display": "妆造 / 状态表达"},
                    {"title": "更优合作对象", "display": "中腰部为主"},
                ],
                "takeaway": "音乐剧创作者不只有剧评博主。真正值得关注的是谁在定义圈层语言，谁在把剧院体验翻译成可感知的状态表达。",
                "left": creator_left,
                "right": creator_right,
                "insights": [
                    "音乐剧内容的影响力并不只掌握在头部垂类博主手里，中腰部创作者更容易带来可信且自然的场景种草。",
                    "圈层发声者负责定义什么是“懂”，状态表达型创作者负责把“懂”翻译成更可感知的生活方式内容。",
                    "对美妆而言，更值得保留的是那些能稳定呈现妆造、出片、赴约与演后情绪的作者样本。",
                ],
                "brand_moves": [
                    "美妆启发：优先关注能承接妆造、重要夜晚和状态表达的作者，而不是只会讲作品信息的账号。",
                ],
            },
            "cross": {
                "kpi": [
                    {"title": "最强连接", "display": cross_rows[0]['name'] if cross_rows else '穿搭妆造'},
                    {"title": "重要场合关联", "display": "强"},
                    {"title": "状态表达浓度", "display": "高"},
                    {"title": "美妆可转译度", "display": "高"},
                ],
                "takeaway": "音乐剧人群天然会向穿搭妆造、重要夜晚、状态管理和体面感表达延展，这意味着他们不是单一内容兴趣，而是完整的自我呈现场景用户。",
                "rows": cross_rows,
                "translations": [
                    "对美妆而言，音乐剧不是“娱乐热点”，而是可以承接妆造、状态和自我呈现的一种内容语境。",
                    "更值得沟通的不是成分解释，而是重要场合下的状态、留香、光影和体面感。",
                    "更有效的内容切口不是“我支持音乐剧”，而是“我懂观演前后的那种状态管理”。",
                ],
                "insights": [
                    "音乐剧人群的跨兴趣指向非常清晰：他们愿意为妆造、留香、状态和重要夜晚的完整感投入注意力。",
                    "这类人群并不追求高调炫耀，更在意精致、克制、有细节的体面感表达。",
                    "因此最有效的美妆切口不是夸张舞台化，而是体面松弛、状态在线和场景完整。",
                ],
                "brand_moves": [
                    "美妆启发：与其扩展到泛生活方式，不如抓紧穿搭妆造、重要夜晚、状态管理和体面感表达这几条强连接。",
                ],
            },
            "comparison": {
                "kpi": [
                    {"title": "对照组", "display": "话剧"},
                    {"title": "对照口径", "display": "同窗同规"},
                    {"title": "比较维度", "display": "5 项"},
                    {"title": "结论性质", "display": "代理对照"},
                ],
                "takeaway": "与邻近剧场圈层相比，音乐剧更偏术语驱动、攻略驱动和仪式感驱动，因此更适合作为高端品牌的内容切入场景之一。",
                "rows": comparison_rows,
                "insights": [
                    "对照组的意义不是证明转化一定更高，而是证明音乐剧不是普通文化消费人群的随机切片。",
                    "如果音乐剧在攻略收藏、术语密度和场景连接上持续高于话剧，就更能支撑其‘高审美、强圈层语言’特征。",
                    "这也解释了为什么音乐剧比话剧更容易承接重要场合、审美表达和仪式感相关的美妆场景。 "
                ],
                "brand_moves": [
                    "美妆启发：相比话剧，音乐剧更适合承接重要场合、审美表达与仪式感相关的美妆语境。 "
                ],
            },
            "playbook": {
                "kpi": [
                    {"title": "进入原则", "display": "3 条"},
                    {"title": "场景主线", "display": "3 段"},
                    {"title": "进入顺序", "display": "先场景后产品"},
                    {"title": "优先切口", "display": "剧院场景"},
                ],
                "takeaway": "如果美妆品牌想进入音乐剧语境，最有效的方法不是直接贴剧名，而是先进入观演前后 48 小时的真实生活场景。",
                "principles": [
                    "先做剧院场景，再做产品说明，不要反过来。",
                    "先说状态、氛围和感受，再说功能，不要一上来就教育用户。",
                    "先借仪式感和表达欲，再承接产品心智。",
                ],
                "phases": [
                    {"phase": "第一步", "focus": "演前准备", "target": "先占据重要场合准备、妆造与出门前状态"},
                    {"phase": "第二步", "focus": "演中呈现", "target": "再承接剧院光影、自我呈现、出片与体面感表达"},
                    {"phase": "第三步", "focus": "演后余韵", "target": "最后延伸到演后修护、情绪复盘与自我照顾"},
                ],
                "actions": [
                    "先进入剧场场景，再进入产品。",
                    "先说状态和感受，再说功能。",
                    "先借仪式感和表达欲，再承接产品心智。",
                    "避雷：硬蹭热度、泛化追星表达、外行式科普、无关作品的强行联名。",
                ],
                "framework": [
                    {"phase": "演前准备", "goal": "先占据重要场合准备心智", "content_mix": "准备清单 40% / 妆造穿搭 35% / 观演攻略 25%", "creator_mix": "圈层 50% / 状态表达 50%", "deliverables": "准备清单 + 妆造图文 + 演前状态短视频", "core_kpi": "收藏率、准备类关键词覆盖", "secondary_kpi": "求同款、求链接、完读率", "review": "阶段复盘", "adjustment": "若收藏不足，则提高准备清单与工具型表达"},
                    {"phase": "演中呈现", "goal": "承接剧院中的自我呈现", "content_mix": "OOTD / 打卡 45% / 状态表达 35% / 剧院光影 20%", "creator_mix": "圈层 40% / 状态表达 60%", "deliverables": "剧院打卡图文 + 出片短视频 + 妆造合集", "core_kpi": "互动率、出片相关互动", "secondary_kpi": "保存率、状态表达评论", "review": "阶段复盘", "adjustment": "若互动不足，则强化光影、妆造和体面感表达"},
                    {"phase": "演后余韵", "goal": "延长情绪与修护场景", "content_mix": "Repo / 情绪 40% / 演后修护 35% / 安利余韵 25%", "creator_mix": "圈层 55% / 状态表达 45%", "deliverables": "演后长文 + 修护内容 + 情绪余韵短帖", "core_kpi": "评论质量、收藏量", "secondary_kpi": "二次提及、情绪复盘深度", "review": "阶段复盘", "adjustment": "若情绪承接弱，则增加第一人称复盘与演后照顾表达"},
                ],
            },
            "risks": {
                "kpi": [
                    {"title": "规模风险", "display": "中"},
                    {"title": "城市供给风险", "display": "高"},
                    {"title": "外溢风险", "display": "中高"},
                    {"title": "装懂风险", "display": "高"},
                ],
                "takeaway": "音乐剧适合做高质量、强场景、强内容密度的品牌进入，但未必天然适合全国性大水漫灌式投放。",
                "rows": [
                    {"label": "圈层规模", "value": "足以支撑内容型策略，但是否支撑全国媒介放量仍需结合城市供给与品牌目标判断"},
                    {"label": "城市供给差异", "value": "上海、北京、广州等城市剧目供给更稳定，其他城市内容连续性可能受限"},
                    {"label": "外溢性", "value": "圈层表达浓度高，若不做生活方式翻译，可能只在内部高认同、外部低扩散"},
                    {"label": "装懂风险", "value": "品牌若直接硬贴剧名或滥用黑话，极易被质疑只是在借势"},
                    {"label": "美妆边界", "value": "若品牌与重要场合、状态管理、自我呈现场景连接弱，则更适合节点借势而非长期深耕"},
                ],
                "insights": [
                    "音乐剧人群有价值，但不是‘只要有钱就值得全国铺开’的大盘型赛道。",
                    "它更适合高端品牌做内容心智和场景占位，而不适合只靠单次大曝光验证。",
                    "真正的风险不是圈层太小，而是品牌进入方式过外行，导致高认同人群先反感。"
                ],
                "brand_moves": [
                    "美妆启发：若品牌与重要场合、状态管理、自我呈现场景连接弱，更适合节点借势，不适合长期深耕。"
                ],
            },
        }
    finally:
        db.close()


def _html(report: dict[str, Any]) -> str:
    hero = report["hero"]
    executive = report["executive"]
    market = report["market"]
    culture = report["culture"]
    content = report["content"]
    topics = report["topics"]
    needs = report["needs"]
    creators = report["creators"]
    cross = report["cross"]
    comparison = report["comparison"]
    playbook = report["playbook"]
    risks = report["risks"]

    nav_items = [
        ("cover", "封面"),
        ("executive", "执行摘要"),
        ("market", "01 · 圈层大盘与生命周期"),
        ("culture", "02 · 圈层文化与语言系统"),
        ("content", "03 · PO 文内容生态"),
        ("topics", "04 · 话题结构与趋势变化"),
        ("needs", "05 · 人群需求与决策链路"),
        ("creators", "06 · 创作者生态与达人策略"),
        ("cross", "07 · 跨兴趣与商业转译"),
        ("comparison", "08 · 邻近圈层对照"),
        ("playbook", "09 · 美妆品牌进入原则"),
        ("risks", "10 · 适用边界与风险"),
    ]
    toc_html = "".join(f'<li><a href="#{_escape(anchor)}">{_escape(label)}</a></li>' for anchor, label in nav_items)

    culture_dict_rows = []
    for item in culture.get("lexicon", []):
        culture_dict_rows.append(
            "<div class=\"culture-chip\">"
            f"<div class=\"culture-term\">{_escape(item.get('label', '-'))}</div>"
            f"<div class=\"culture-count mono\">{_escape(item.get('value', '-'))}</div>"
            f"<div class=\"culture-meaning\">{_escape(item.get('meaning', '-'))}</div>"
            "</div>"
        )
    topic_rising = "<div class=\"card\"><div class=\"card-title\">最近上涨的话题</div>" + _render_snapshot_rows(topics.get("rising", [])) + "</div>"
    needs_journey = "<div class=\"card\"><div class=\"card-title\">用户决策链路</div>" + _render_snapshot_rows(needs.get("journey", [])) + "</div>"
    cross_translation = "<div class=\"card amber\"><div class=\"card-title\">与美妆最相关的转译</div>" + _render_list(cross.get("translations", [])) + "</div>"
    playbook_principles = "<div class=\"card blue\"><div class=\"card-title\">进入原则</div>" + _render_list(playbook.get("principles", [])) + "</div>"
    comparison_table = "<div class=\"card\"><div class=\"card-title\">音乐剧 vs 话剧</div>" + _render_compare_rows(comparison.get("rows", [])) + "</div>"
    playbook_framework = "<div class=\"card\"><div class=\"card-title\">90天执行框架</div>" + _render_framework_rows(playbook.get("framework", [])) + "</div>"

    html_doc = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>小红书 × 音乐剧洞察报告</title>
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
<link href=\"https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap\" rel=\"stylesheet\">
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
  --purple: #a78bfa;
  --green: #22c55e;
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
.skip-link {{ position: absolute; left: 12px; top: -48px; background: #fff; color: #111; font-weight: 700; padding: 8px 10px; border-radius: 8px; z-index: 999; }}
.skip-link:focus-visible {{ top: 12px; }}
.nav {{ width: var(--nav-w); position: fixed; top: 0; left: 0; bottom: 0; background: var(--bg2); border-right: 1px solid var(--line); padding: 28px 16px 24px; z-index: 100; overflow-y: auto; }}
.nav-brand {{ background: linear-gradient(135deg, var(--blue2) 0%, #1a2880 100%); border-radius: var(--radius-sm); padding: 14px 16px; margin-bottom: 24px; border: 1px solid rgba(79,125,255,0.25); }}
.nav-brand .nb-tag {{ font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(255,255,255,0.55); font-family: 'DM Mono', monospace; }}
.nav-brand .nb-name {{ font-size: 17px; font-weight: 700; color: #fff; margin-top: 4px; letter-spacing: -0.02em; }}
.nav-brand .nb-sub {{ font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 6px; }}
.nav-toc {{ list-style: none; }}
.nav-toc li {{ margin: 2px 0; }}
.nav-toc a {{ display: block; padding: 8px 12px; border-radius: 8px; font-size: 12.5px; color: var(--text2); transition: color .2s ease, background-color .2s ease, border-color .2s ease; border: 1px solid transparent; }}
.nav-toc a:hover,.nav-toc a:focus-visible,.nav-toc a.active {{ color: var(--blue); background: var(--blue-g); border-color: rgba(79,125,255,0.15); outline: 2px solid transparent; }}
.nav-toc .toc-part {{ font-size: 10px; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text3); padding: 14px 12px 4px; }}
.main {{ margin-left: var(--nav-w); min-height: 100vh; }}
.hero {{ min-height: 100vh; background: radial-gradient(ellipse at 80% 20%, rgba(79,125,255,0.12) 0%, transparent 50%), radial-gradient(ellipse at 10% 80%, rgba(245,166,35,0.07) 0%, transparent 45%), var(--bg); border-bottom: 1px solid var(--line); display: flex; flex-direction: column; justify-content: center; padding: 80px 64px 64px; position: relative; overflow: hidden; }}
.hero-grid-bg {{ position: absolute; inset: 0; opacity: 0.03; background-image: linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px); background-size: 40px 40px; }}
.hero-chip {{ display: inline-flex; align-items: center; gap: 8px; background: var(--blue-g); border: 1px solid rgba(79,125,255,0.25); border-radius: 999px; padding: 6px 14px; font-size: 11px; font-family: 'DM Mono', monospace; letter-spacing: 0.1em; color: var(--blue); text-transform: uppercase; margin-bottom: 28px; }}
.hero-chip::before {{ content: '●'; font-size: 8px; }}
.hero h1 {{ font-size: 58px; font-weight: 800; line-height: 1.04; letter-spacing: -0.04em; color: #fff; max-width: 900px; text-wrap: balance; }}
.hero h1 span {{ color: var(--blue); }}
.hero-desc {{ max-width: 820px; margin-top: 20px; font-size: 17px; color: var(--text2); line-height: 1.75; }}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }}
.hero-tag {{ font-size: 12px; padding: 5px 12px; border-radius: 6px; border: 1px solid var(--line2); color: var(--text2); font-family: 'DM Mono', monospace; }}
.hero-stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-top: 40px; max-width: 980px; }}
.hstat {{ background: var(--bg3); border: 1px solid var(--line2); border-radius: var(--radius-sm); padding: 18px 20px; }}
.hstat-num {{ font-size: 28px; font-weight: 700; color: #fff; font-family: 'DM Mono', monospace; letter-spacing: -0.03em; }}
.hstat-label {{ font-size: 11px; color: var(--text3); margin-top: 4px; }}
.section {{ padding: 72px 64px; border-bottom: 1px solid var(--line); scroll-margin-top: 24px; }}
.section:last-child {{ border-bottom: none; }}
.section-kicker {{ font-size: 11px; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.14em; color: var(--blue); margin-bottom: 10px; }}
.section h2 {{ font-size: 32px; font-weight: 700; letter-spacing: -0.03em; color: #fff; margin-bottom: 10px; line-height: 1.2; text-wrap: balance; }}
.section-desc {{ font-size: 14px; color: var(--text2); max-width: 860px; line-height: 1.7; margin-bottom: 24px; }}
.grid2 {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }}
.grid3 {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; }}
.grid4 {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }}
.section-grid-gap {{ margin-top: 16px; }}
.card {{ background: var(--bg3); border: 1px solid var(--line2); border-radius: var(--radius); padding: 24px; min-width: 0; }}
.card.blue {{ border-color: rgba(79,125,255,0.25); background: rgba(79,125,255,0.06); }}
.card.amber {{ border-color: rgba(245,166,35,0.25); background: rgba(245,166,35,0.05); }}
.card.teal {{ border-color: rgba(45,212,191,0.2); background: rgba(45,212,191,0.05); }}
.card.red {{ border-color: rgba(255,95,109,0.2); background: rgba(255,95,109,0.05); }}
.card-title {{ font-size: 13px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}
.card-value {{ font-size: 26px; font-weight: 700; font-family: 'DM Mono', monospace; color: #fff; }}
.insight-box {{ background: var(--bg4); border-left: 3px solid var(--blue); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 14px 18px; margin-top: 18px; }}
.ib-label {{ font-size: 10px; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text3); margin-bottom: 6px; }}
.ib-text {{ font-size: 14px; color: var(--text); line-height: 1.7; }}
.mono {{ font-family: 'DM Mono', monospace; font-variant-numeric: tabular-nums; }}
.action-list {{ margin-left: 18px; }}
.action-list li {{ margin: 7px 0; color: #d8d8e8; }}
.kv-row {{ display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-bottom: 1px solid var(--line); }}
.kv-row:last-child {{ border-bottom: none; }}
.kv-key {{ color: var(--text2); min-width: 0; }}
.kv-value {{ color: #fff; text-align: right; min-width: 0; word-break: break-word; }}
.week-chart {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(44px, 1fr)); align-items: end; gap: 10px; min-height: 220px; }}
.week-bar {{ display: flex; flex-direction: column; align-items: center; justify-content: end; min-width: 0; }}
.week-bar-fill {{ width: 100%; border-radius: 10px 10px 4px 4px; background: linear-gradient(180deg, var(--blue) 0%, var(--purple) 100%); }}
.week-bar-num {{ font-size: 10px; color: var(--text3); margin-top: 8px; }}
.week-bar-label {{ font-size: 10px; color: var(--text2); margin-top: 2px; }}
.score-bar-row {{ display: grid; grid-template-columns: minmax(160px, 230px) 1fr 76px; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); }}
.score-bar-row:last-child {{ border-bottom: none; }}
.score-bar-main {{ min-width: 0; }}
.score-bar-name {{ font-size: 13px; font-weight: 600; color: #fff; }}
.bar-aux {{ font-size: 11px; color: var(--text3); margin-top: 2px; line-height: 1.5; word-break: break-word; }}
.score-bar-track {{ height: 10px; border-radius: 999px; background: var(--bg4); overflow: hidden; }}
.score-bar-fill {{ height: 10px; border-radius: 999px; background: linear-gradient(90deg, var(--blue), var(--purple)); }}
.score-bar-value {{ font-size: 13px; color: #fff; text-align: right; }}
.culture-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }}
.culture-chip {{ border: 1px solid var(--line2); border-radius: 12px; padding: 14px; background: var(--bg4); }}
.culture-term {{ font-size: 16px; font-weight: 700; color: #fff; }}
.culture-count {{ font-size: 11px; color: var(--amber); margin-top: 4px; }}
.culture-meaning {{ font-size: 12px; color: var(--text2); line-height: 1.7; margin-top: 8px; }}
.type-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }}
.type-card .type-meta {{ font-size: 12px; color: var(--text3); margin-bottom: 12px; }}
.type-grid-mini {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }}
.mini-label {{ font-size: 11px; color: var(--text3); margin-bottom: 4px; }}
.mini-value {{ font-size: 18px; color: #fff; }}
.sample-grid {{ align-items: start; }}
.sample-card {{ display: flex; flex-direction: column; gap: 12px; }}
.sample-group-desc {{ font-size: 13px; color: var(--text2); line-height: 1.7; }}
.sample-group-count {{ font-size: 11px; color: var(--text3); }}
.sample-list {{ display: flex; flex-direction: column; gap: 12px; }}
.sample-row {{ display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; border-top: 1px solid var(--line); padding-top: 12px; }}
.sample-copy {{ min-width: 0; flex: 1; }}
.sample-title {{ font-size: 13px; font-weight: 600; color: #fff; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.sample-summary {{ font-size: 12px; color: var(--text2); margin-top: 4px; line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
.sample-meta,.sample-stats {{ font-size: 11px; color: var(--text3); margin-top: 6px; }}
.sample-link {{ display: inline-flex; align-items: center; justify-content: center; white-space: nowrap; border-radius: 999px; border: 1px solid rgba(79,125,255,0.25); background: var(--blue-g); color: var(--blue); padding: 8px 12px; font-size: 11px; font-family: 'DM Mono', monospace; transition: background-color .2s ease, color .2s ease, border-color .2s ease, transform .2s ease; }}
.sample-link:hover,.sample-link:focus-visible {{ background: rgba(79,125,255,0.18); border-color: rgba(79,125,255,0.40); color: #dfe7ff; outline: 2px solid rgba(79,125,255,0.28); outline-offset: 2px; }}
.sample-link:active {{ transform: translateY(1px); }}
.creator-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }}
.creator-col {{ display: grid; gap: 10px; }}
.creator-card {{ border: 1px solid var(--line2); border-radius: 12px; padding: 14px; background: var(--bg4); display: grid; gap: 8px; }}
.creator-name {{ font-size: 14px; font-weight: 600; color: #fff; }}
.creator-meta {{ font-size: 11px; color: var(--text3); line-height: 1.6; }}
.definition-row {{ padding: 12px 0; border-bottom: 1px solid var(--line); }}
.definition-row:last-child {{ border-bottom: none; }}
.definition-name {{ font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 4px; }}
.definition-text {{ font-size: 12px; color: var(--text2); line-height: 1.7; }}
.compare-table {{ display: grid; gap: 0; }}
.compare-row {{ display: grid; grid-template-columns: 160px 110px 110px 1fr; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--line); align-items: start; }}
.compare-head {{ padding-top: 0; }}
.compare-head div {{ color: var(--text3); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
.compare-metric {{ color: #fff; font-size: 13px; font-weight: 600; }}
.compare-cell {{ color: var(--text2); font-size: 12px; line-height: 1.7; }}
.framework-wrap {{ display: grid; gap: 12px; }}
.framework-card {{ border: 1px solid var(--line2); border-radius: 14px; background: var(--bg4); padding: 16px; }}
.framework-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px 16px; margin-top: 12px; }}
.framework-grid span {{ display: block; font-size: 11px; color: var(--text3); margin-bottom: 4px; }}
.framework-grid strong {{ display: block; font-size: 12px; line-height: 1.7; color: #fff; font-weight: 500; }}
.phase-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; }}
.phase-card {{ border: 1px solid var(--line2); border-radius: 10px; background: var(--bg4); padding: 12px; }}
.phase-title {{ font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
.phase-focus {{ font-size: 12px; color: var(--text2); margin-bottom: 6px; }}
.phase-target {{ font-size: 12px; color: #dcdcf0; }}
.empty-box {{ border: 1px dashed var(--line2); border-radius: 12px; padding: 18px; color: var(--text3); }}
@media (max-width: 1280px) {{ .section, .hero {{ padding-left: 36px; padding-right: 36px; }} .hero h1 {{ font-size: 46px; }} .type-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
@media (max-width: 1080px) {{ .nav {{ position: sticky; width: 100%; height: auto; max-height: 42vh; }} .main {{ margin-left: 0; }} .hero {{ min-height: auto; padding-top: 46px; }} .grid4 {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} .grid3 {{ grid-template-columns: 1fr; }} .grid2 {{ grid-template-columns: 1fr; }} .type-grid {{ grid-template-columns: 1fr; }} .creator-grid {{ grid-template-columns: 1fr; }} .phase-grid {{ grid-template-columns: 1fr; }} .culture-grid {{ grid-template-columns: 1fr; }} .score-bar-row {{ grid-template-columns: 1fr; }} .sample-row {{ flex-direction: column; }} .sample-link {{ width: 100%; }} .hero-stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .compare-row {{ grid-template-columns: 1fr; }} .framework-grid {{ grid-template-columns: 1fr; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }} }}
</style>
</head>
<body>
<a class=\"skip-link\" href=\"#main\">跳到正文</a>
<nav class=\"nav\" aria-label=\"章节导航\">
  <div class=\"nav-brand\">
    <div class=\"nb-tag\">XHS Audience Insight</div>
    <div class=\"nb-name\">小红书 × 音乐剧洞察报告</div>
    <div class=\"nb-sub\">人群洞察与营销打法</div>
  </div>
  <ul class=\"nav-toc\" id=\"toc\">{toc_html}</ul>
</nav>
<main class=\"main\" id=\"main\">
  <section class=\"hero\" id=\"cover\">
    <div class=\"hero-grid-bg\" aria-hidden=\"true\"></div>
    <div class=\"hero-chip\">{_escape(hero['chip'])}</div>
    <h1><span>小红书 × 音乐剧洞察报告</span></h1>
    <p class=\"hero-desc\">{_escape(hero['desc'])}</p>
    <div class=\"hero-meta">{''.join(f'<span class="hero-tag">{_escape(tag)}</span>' for tag in hero.get('tags', []))}</div>
    <div class=\"hero-stats\">{_render_kpi_cards(executive['kpi'])}</div>
  </section>
  {_section('executive', '封面 · 执行摘要', '执行摘要', '', executive['kpi'], executive['takeaway'], '<div class="grid2 section-grid-gap"><div class="card blue"><div class="card-title">三条核心结论</div>' + _render_list(executive['findings']) + '</div><div class="card amber"><div class="card-title">对美妆的总体启发</div>' + _render_list(executive['actions'], ordered=True) + '</div></div>')}
  {_section('market', '01 · 圈层大盘与生命周期', '圈层大盘与生命周期', '先判断音乐剧是不是值得持续投入的内容池。', market['kpi'], market['takeaway'], '<div class="grid2 section-grid-gap"><div class="card"><div class="card-title">近90天周度热度</div>' + _render_weekly_bars(market['weekly'], 'notes') + '</div><div class="card"><div class="card-title">近90天周度互动</div>' + _render_weekly_bars(market['weekly'], 'interactions') + '</div></div><div class="grid2 section-grid-gap"><div class="card"><div class="card-title">盘面判断</div>' + _render_snapshot_rows(market['support']) + '</div><div class="card"><div class="card-title">阶段结论</div><div class="ib-text">' + _escape(market['callout']) + '</div></div></div>' + _render_strategy_cards(market['insights'], market['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('culture', '02 · 圈层文化与语言系统', '圈层文化与语言系统', '先看懂他们怎么说，才知道这群人的审美与礼仪感从哪里来。', culture['kpi'], culture['takeaway'], '<div class="culture-grid section-grid-gap">' + ''.join(culture_dict_rows) + '</div><div class="grid2 section-grid-gap"><div class="card"><div class="card-title">真实高频词</div>' + _render_snapshot_rows(culture['terms']) + '</div><div class="card red"><div class="card-title">圈层雷区</div>' + _render_list(culture['taboos']) + '</div></div><div class="section-grid-gap">' + _render_sample_groups(culture['samples']) + '</div>' + _render_strategy_cards(culture['insights'], culture['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('content', '03 · PO 文内容生态', 'PO 文内容生态', '主标签与副标签拆开定义，避免同一条内容在不同章节反复解释。', content['kpi'], content['takeaway'], '<div class="type-grid section-grid-gap">' + ''.join(f'<article class="card type-card {'blue' if idx == 0 else 'amber' if idx == 1 else 'teal' if idx == 2 else ''}"><div class="card-title">{_escape(item["name"])}</div><div class="type-meta mono">占比 {_escape(_fmt_pct(item["share"], 1))} · 样本 {_escape(_fmt_num(item["notes"]))}</div><div class="type-grid-mini"><div><div class="mini-label">篇均互动</div><div class="mini-value mono">{_escape(_fmt_score(item["avg_inter"], 1))}</div></div><div><div class="mini-label">篇均收藏</div><div class="mini-value mono">{_escape(_fmt_score(item["avg_save"], 1))}</div></div></div><div class="sample-group-desc" style="margin-top:12px;">{_escape(item["formula"])}</div></article>' for idx, item in enumerate(content['types'])) + '</div><div class="grid2 section-grid-gap"><div class="card blue"><div class="card-title">内容公式</div>' + _render_list(content['formulas']) + '</div><div class="card"><div class="card-title">分类口径</div>' + _render_snapshot_rows(content['taxonomy']) + '</div></div><div class="section-grid-gap">' + _render_sample_groups(content['samples']) + '</div>' + _render_strategy_cards(content['insights'], content['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('topics', '04 · 话题结构与趋势变化', '话题结构与趋势变化', '判断音乐剧人群最近在聊什么，以及哪些话题正在往状态表达扩张。', topics['kpi'], topics['takeaway'], '<div class="grid2 section-grid-gap"><div class="card"><div class="card-title">核心话题分布</div>' + _render_bar_rows(topics['rows']) + '</div>' + topic_rising + '</div><div class="section-grid-gap">' + _render_sample_groups(topics['samples']) + '</div>' + _render_strategy_cards(topics['insights'], topics['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('needs', '05 · 人群需求与决策链路', '人群需求与决策链路', '把需求放回真实链路里看，才看得见三段最关键的场景。', needs['kpi'], needs['takeaway'], '<div class="grid2 section-grid-gap"><div class="card"><div class="card-title">需求分布</div>' + _render_bar_rows(needs['rows']) + '</div>' + needs_journey + '</div><div class="section-grid-gap">' + _render_sample_groups(needs['samples']) + '</div>' + _render_strategy_cards(needs['insights'], needs['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('creators', '06 · 创作者生态与达人策略', '创作者生态与达人策略', '谁在定义圈层，谁更擅长把剧院体验翻译成状态表达。', creators['kpi'], creators['takeaway'], _render_creator_columns(creators['left'], creators['right']) + _render_strategy_cards(creators['insights'], creators['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('cross', '07 · 跨兴趣与商业转译', '跨兴趣与商业转译', '把跨兴趣收窄到与美妆最相关的生活方式连接。', cross['kpi'], cross['takeaway'], '<div class="grid2 section-grid-gap"><div class="card"><div class="card-title">与美妆最相关的生活方式连接</div>' + _render_bar_rows([{"name": item["name"], "value": item["score"], "aux": "共现强度"} for item in cross['rows']], 'value') + '</div>' + cross_translation + '</div>' + _render_strategy_cards(cross['insights'], cross['brand_moves'], '人群洞察', '美妆启发'))}
  {_section('comparison', '08 · 邻近圈层对照', '邻近圈层对照', '用话剧做唯一邻近剧场圈层对照，判断音乐剧是否具有更鲜明的审美与仪式感特征。', comparison['kpi'], comparison['takeaway'], comparison_table + _render_strategy_cards(comparison['insights'], comparison['brand_moves'], '对照洞察', '美妆启发'))}
  {_section('playbook', '09 · 美妆品牌进入原则', '美妆品牌进入原则', '不先讲怎么投，而先讲美妆品牌该以什么姿态进入。', playbook['kpi'], playbook['takeaway'], '<div class="grid2 section-grid-gap">' + playbook_principles + '<div class="card amber"><div class="card-title">进入顺序</div>' + _render_list(playbook['actions'], ordered=True) + '</div></div>' + playbook_framework + _render_phase_cards(playbook['phases']))}
  {_section('risks', '10 · 适用边界与风险', '适用边界与风险', '', risks['kpi'], risks['takeaway'], '<div class="grid2 section-grid-gap"><div class="card"><div class="card-title">风险清单</div>' + _render_snapshot_rows(risks['rows']) + '</div><div class="card red"><div class="card-title">风险判断</div>' + _render_list(risks['insights']) + '</div></div>' + _render_strategy_cards(risks['insights'], risks['brand_moves'], '边界判断', '美妆启发'))}
</main>
<script>
(function() {{
  const links = [...document.querySelectorAll('#toc a[href^="#"]')];
  const map = new Map(links.map((a) => [a.getAttribute('href').slice(1), a]));
  const sections = [...map.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  const io = new IntersectionObserver((entries) => {{
    entries.forEach((entry) => {{
      const link = map.get(entry.target.id);
      if (!link) return;
      if (entry.isIntersecting) {{
        links.forEach((x) => x.classList.remove('active'));
        link.classList.add('active');
      }}
    }});
  }}, {{ rootMargin: '-35% 0px -55% 0px', threshold: 0.01 }});
  sections.forEach((s) => io.observe(s));
}})();
</script>
</body>
</html>"""
    return html_doc


def main() -> None:
    report = _build_mock_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(_html(report), encoding="utf-8")
    print(f"mock_report={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
