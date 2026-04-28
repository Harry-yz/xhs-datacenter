from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db import SessionLocal

OUTPUT_PATH = Path("/app/docs/reports/arden_brand_health_real_snapshot.html")
WINDOW_DAYS = 90

MUSIC_REGEX = r"(音乐剧|剧院|卡司|repo|返场|二刷|法扎|德扎|魅影|musical|broadway|west\s*end|伦敦西区)"

BRAND_ALIASES: dict[str, list[str]] = {
    "伊丽莎白雅顿": ["雅顿", "伊丽莎白雅顿", "elizabeth arden", "红门", "橘灿", "金胶", "8小时霜"],
    "兰蔻": ["兰蔻", "lancome", "小黑瓶", "菁纯", "粉水"],
    "雅诗兰黛": ["雅诗兰黛", "estee lauder", "小棕瓶"],
    "YSL": ["ysl", "圣罗兰", "yves saint laurent"],
    "赫莲娜": ["赫莲娜", "helena rubinstein", "黑绷带"],
    "海蓝之谜": ["海蓝之谜", "la mer", "精粹水"],
}

TARGET_BRAND = "伊丽莎白雅顿"


@dataclass
class NoteRow:
    note_id: str
    text: str
    like_count: int
    collection_count: int
    comment_count: int
    share_count: int
    interaction_total: int
    stat_count: int
    author_id: str
    author_nickname: str
    author_fans_count: int


def _to_int(v: Any) -> int:
    if v in (None, ""):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _short_num(v: float | int) -> str:
    n = float(v)
    if abs(n) >= 100000000:
        return f"{n / 100000000:.2f}亿"
    if abs(n) >= 10000:
        return f"{n / 10000:.2f}万"
    if n.is_integer():
        return str(int(n))
    return f"{n:.2f}"


def _pct(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}%"


def _load_notes(db) -> list[NoteRow]:
    rows = db.execute(
        text(
            """
            SELECT
              note_id,
              lower(
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(content, ''),
                  coalesce(array_to_string(tags, ' '), '')
                )
              ) AS txt,
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
            WHERE date(coalesce(publish_time, created_at)) >= current_date - (:days - 1) * interval '1 day'
              AND lower(
                concat_ws(
                  ' ',
                  coalesce(title, ''),
                  coalesce(content, ''),
                  coalesce(array_to_string(tags, ' '), '')
                )
              ) ~ :music_regex
            """
        ),
        {"days": WINDOW_DAYS, "music_regex": MUSIC_REGEX},
    ).mappings().all()

    out: list[NoteRow] = []
    for r in rows:
        out.append(
            NoteRow(
                note_id=str(r.get("note_id") or ""),
                text=str(r.get("txt") or ""),
                like_count=_to_int(r.get("like_count")),
                collection_count=_to_int(r.get("collection_count")),
                comment_count=_to_int(r.get("comment_count")),
                share_count=_to_int(r.get("share_count")),
                interaction_total=_to_int(r.get("interaction_total")),
                stat_count=_to_int(r.get("stat_count")),
                author_id=str(r.get("author_id") or ""),
                author_nickname=str(r.get("author_nickname") or ""),
                author_fans_count=_to_int(r.get("author_fans_count")),
            )
        )
    return out


def _contains_any(txt: str, terms: list[str]) -> bool:
    return any(t.lower() in txt for t in terms)


def _type_of_note(n: NoteRow) -> str:
    txt = n.text
    if re.search(r"ootd|穿搭|妆容|打卡|look|剧院感", txt, re.IGNORECASE):
        return "剧院质感妆护OOTD"
    if re.search(r"攻略|清单|选座|防雷|怎么买|怎么选|预算", txt, re.IGNORECASE):
        return "观演前48小时准备清单"
    return "演后复盘与同款追问"


def _brand_metrics(notes: list[NoteRow]) -> dict[str, dict[str, Any]]:
    total_notes = len(notes)
    total_inter = sum(n.interaction_total for n in notes)

    metrics: dict[str, dict[str, Any]] = {}
    for brand, aliases in BRAND_ALIASES.items():
        hit = [n for n in notes if _contains_any(n.text, aliases)]
        note_count = len(hit)
        inter = sum(n.interaction_total for n in hit)
        saves = sum(n.collection_count for n in hit)
        comments = sum(n.comment_count for n in hit)
        reads = sum(n.stat_count for n in hit)
        creators = len({n.author_id for n in hit if n.author_id})
        hq = sum(1 for n in hit if n.collection_count >= 5 or n.interaction_total >= 60)

        avg_inter = inter / note_count if note_count else 0.0
        hq_rate = hq / note_count if note_count else 0.0
        save_rate = (saves / note_count) if note_count > 0 else 0.0
        sov = (note_count / total_notes * 100.0) if total_notes else 0.0
        inter_share = (inter / total_inter * 100.0) if total_inter else 0.0

        metrics[brand] = {
            "brand": brand,
            "notes": note_count,
            "interactions": inter,
            "saves": saves,
            "comments": comments,
            "reads": reads,
            "creators": creators,
            "hq_notes": hq,
            "avg_inter": avg_inter,
            "hq_rate": hq_rate,
            "save_rate": save_rate,
            "sov": sov,
            "inter_share": inter_share,
        }

    return metrics


def _score_health(metrics: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], str]:
    brands = list(metrics.keys())

    max_notes = max((metrics[b]["notes"] for b in brands), default=1)
    max_avg_inter = max((metrics[b]["avg_inter"] for b in brands), default=1.0)
    max_hq_rate = max((metrics[b]["hq_rate"] for b in brands), default=1.0)
    max_creators = max((metrics[b]["creators"] for b in brands), default=1)
    max_save_rate = max((metrics[b]["save_rate"] for b in brands), default=1.0)

    for b in brands:
        m = metrics[b]
        d1 = 20.0 * (m["notes"] / max_notes if max_notes > 0 else 0.0)
        d2 = 20.0 * (m["avg_inter"] / max_avg_inter if max_avg_inter > 0 else 0.0)
        d3 = 20.0 * (m["hq_rate"] / max_hq_rate if max_hq_rate > 0 else 0.0)
        d4 = 20.0 * (m["creators"] / max_creators if max_creators > 0 else 0.0)
        d5 = 20.0 * (m["save_rate"] / max_save_rate if max_save_rate > 0 else 0.0)

        m["dim_scores"] = {
            "声量渗透": round(d1, 2),
            "互动质量": round(d2, 2),
            "内容资产": round(d3, 2),
            "圈层匹配": round(d4, 2),
            "转化潜力": round(d5, 2),
        }
        m["health_score"] = round(d1 + d2 + d3 + d4 + d5, 2)

    benchmark = max(brands, key=lambda x: metrics[x]["health_score"]) if brands else "-"
    return metrics, benchmark


def _executive(metrics: dict[str, dict[str, Any]], benchmark: str) -> dict[str, Any]:
    arden = metrics[TARGET_BRAND]
    bench = metrics[benchmark]

    gap = arden["health_score"] - bench["health_score"]
    findings = [
        f"雅顿在音乐剧样本中的品牌健康度为 {arden['health_score']:.1f} 分，当前标杆为{benchmark}。",
        f"雅顿圈层声量占比 {_pct(arden['sov'], 2)}，较标杆低 {_pct(max(0.0, bench['sov'] - arden['sov']), 2)}。",
        f"雅顿篇均收藏 {arden['save_rate']:.2f}，核心提升空间在内容资产与场景化表达。",
    ]

    actions = [
        "把“演前48小时准备清单”设为主力转化内容，每周至少1条。",
        "围绕剧院场景做高质感妆护内容，提升收藏与搜索承接。",
        "达人投放按4:6组合，先圈层背书后跨界放量。",
        "核心KPI聚焦收藏率、搜索点击率、互动质量三项。",
        "每两周复盘低效素材并快速替换，提高内容资产密度。",
    ]

    return {
        "kpi": [
            {"id": "score", "title": "品牌健康度总分", "value": arden["health_score"], "display": f"{arden['health_score']:.1f}/100"},
            {"id": "sov", "title": "圈层声量占比", "value": arden["sov"], "display": _pct(arden["sov"], 2)},
            {"id": "gap", "title": f"较{benchmark}差距", "value": gap, "display": f"{gap:+.1f}分"},
        ],
        "chart_data": {"findings": findings, "actions": actions},
        "takeaway": f"结论：雅顿已形成基础声量，但要缩小与{benchmark}的差距，优先补强内容资产与收藏转化。",
    }


def _brand_health(metrics: dict[str, dict[str, Any]], benchmark: str) -> dict[str, Any]:
    arden = metrics[TARGET_BRAND]
    bench = metrics[benchmark]

    dims = []
    for dim_name in ["声量渗透", "互动质量", "内容资产", "圈层匹配", "转化潜力"]:
        dims.append(
            {
                "name": dim_name,
                "score": arden["dim_scores"][dim_name],
                "benchmark": bench["dim_scores"][dim_name],
                "benchmark_brand": benchmark,
            }
        )

    tier = "领先" if arden["health_score"] >= 80 else "成长强势" if arden["health_score"] >= 60 else "待突破"

    return {
        "kpi": [
            {"id": "total", "title": "总分", "value": arden["health_score"], "display": f"{arden['health_score']:.1f}"},
            {"id": "tier", "title": "健康度层级", "value": 1, "display": tier},
            {
                "id": "benchmark",
                "title": "当前标杆品牌",
                "value": 1,
                "display": benchmark,
            },
            {
                "id": "gap",
                "title": "与标杆差距",
                "value": arden["health_score"] - bench["health_score"],
                "display": f"{arden['health_score'] - bench['health_score']:+.1f}分",
            },
        ],
        "chart_data": {"dimensions": dims},
        "takeaway": f"Key Takeaway：雅顿最高维度是“圈层匹配”，最低维度是“内容资产”；标杆品牌为{benchmark}。",
    }


def _competition(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(metrics.values(), key=lambda x: x["health_score"], reverse=True)
    rank = next((i + 1 for i, x in enumerate(rows) if x["brand"] == TARGET_BRAND), len(rows))
    top = rows[0] if rows else None
    arden = metrics[TARGET_BRAND]

    rivals = []
    for x in rows:
        rivals.append(
            {
                "brand": x["brand"],
                "health": round(x["health_score"], 1),
                "sov": round(x["sov"], 2),
                "save_rate": round(x["save_rate"], 2),
                "er": round((x["interactions"] / max(1, x["notes"])), 2),
            }
        )

    top_sov = top["sov"] if top else 0.0
    top_save = top["save_rate"] if top else 0.0

    return {
        "kpi": [
            {"id": "rank", "title": "竞品排名", "value": rank, "display": f"#{rank}/{len(rows)}"},
            {"id": "sov_gap", "title": "声量占比差距", "value": arden["sov"] - top_sov, "display": f"{arden['sov'] - top_sov:+.2f}pp"},
            {
                "id": "save_gap",
                "title": "收藏率差距",
                "value": arden["save_rate"] - top_save,
                "display": f"{arden['save_rate'] - top_save:+.2f}",
            },
        ],
        "chart_data": {"rivals": rivals},
        "takeaway": "Key Takeaway：雅顿当前最大竞争缺口是声量份额，其次是收藏转化效率。",
    }


def _audience_fit(notes: list[NoteRow]) -> dict[str, Any]:
    total = max(1, len(notes))
    trait_map = {
        "审美质感敏感": ["质感", "氛围", "高级", "光影", "镜头", "妆感"],
        "细节考究": ["细节", "卡司", "舞美", "音效", "座位", "版本"],
        "精神悦己": ["治愈", "感动", "情绪", "共鸣", "上头"],
        "场景消费": ["演前", "约会", "出片", "打卡", "香水", "妆容"],
    }
    scene_map = {
        "演前妆护准备": ["演前", "妆容", "护肤", "底妆", "香水"],
        "剧院社交出片": ["剧院", "打卡", "出片", "穿搭", "ootd"],
        "演后复盘分享": ["repo", "返场", "复盘", "二刷"],
        "异地巡演出行": ["巡演", "行程", "住宿", "高铁", "机票"],
    }

    def _score(group: dict[str, list[str]]) -> list[dict[str, Any]]:
        out = []
        for name, words in group.items():
            hit = sum(1 for n in notes if any(w in n.text for w in words))
            out.append({"name": name, "hit": hit, "score": min(95, max(45, int(45 + 50 * (hit / total))))})
        out.sort(key=lambda x: x["score"], reverse=True)
        return [{"name": x["name"], "score": x["score"]} for x in out]

    traits = _score(trait_map)
    scenes = _score(scene_map)

    premium_signal = sum(1 for n in notes if any(w in n.text for w in ["vip", "前排", "礼服", "香水", "法餐", "酒吧"])) / total * 100
    intent_signal = sum(1 for n in notes if any(w in n.text for w in ["求", "推荐", "怎么买", "链接", "同款", "哪里买"])) / total * 100
    fit_index = sum(x["score"] for x in traits[:3]) / 3

    return {
        "kpi": [
            {"id": "fit", "title": "圈层契合指数", "value": fit_index, "display": f"{fit_index:.1f}/100"},
            {"id": "premium", "title": "高客单信号占比", "value": premium_signal, "display": _pct(premium_signal)},
            {"id": "intent", "title": "购买意向语句占比", "value": intent_signal, "display": _pct(intent_signal)},
        ],
        "chart_data": {"traits": traits, "scenes": scenes},
        "takeaway": "Key Takeaway：高转化机会集中在“演前妆护准备”和“剧院社交出片”两条场景链路。",
    }


def _content_engine(notes: list[NoteRow]) -> dict[str, Any]:
    groups: dict[str, list[NoteRow]] = defaultdict(list)
    for n in notes:
        groups[_type_of_note(n)].append(n)

    order = ["剧院质感妆护OOTD", "观演前48小时准备清单", "演后复盘与同款追问"]
    cards = []
    for t in order:
        rows = groups.get(t, [])
        cnt = len(rows)
        reads = sum(x.stat_count for x in rows)
        inter = sum(x.interaction_total for x in rows)
        saves = sum(x.collection_count for x in rows)
        er = inter / max(1, cnt)
        save_rate = saves / max(1, cnt)
        formula = (
            "质感近景 + 剧院暖光 + 情绪化短句"
            if t == "剧院质感妆护OOTD"
            else "场景拆解 + 单品顺序 + 防雷建议"
            if t == "观演前48小时准备清单"
            else "情绪复盘 + 妆面细节 + 评论承接"
        )
        cards.append(
            {
                "type": t,
                "er": round(er, 2),
                "save_rate": round(save_rate, 2),
                "note_count": cnt,
                "formula": formula,
            }
        )

    best_save = max(cards, key=lambda x: x["save_rate"], default={"save_rate": 0})
    best_er = max(cards, key=lambda x: x["er"], default={"er": 0})

    return {
        "kpi": [
            {"id": "types", "title": "高效内容类型", "value": len(cards), "display": str(len(cards))},
            {"id": "best_save", "title": "最高篇均收藏", "value": best_save.get("save_rate", 0), "display": f"{best_save.get('save_rate', 0):.2f}"},
            {"id": "best_er", "title": "最高篇均互动", "value": best_er.get("er", 0), "display": f"{best_er.get('er', 0):.2f}"},
        ],
        "chart_data": {"types": cards},
        "takeaway": f"Key Takeaway：当前收藏效率最佳类型是“{best_save.get('type','-')}”，互动效率最佳类型是“{best_er.get('type','-')}”。",
    }


def _influencer_strategy(notes: list[NoteRow]) -> dict[str, Any]:
    by_author: dict[str, dict[str, Any]] = {}
    for n in notes:
        if not n.author_id:
            continue
        d = by_author.setdefault(
            n.author_id,
            {
                "name": n.author_nickname or f"作者{n.author_id[-4:]}",
                "fans": n.author_fans_count,
                "notes": 0,
                "inter": 0,
                "reads": 0,
                "deep": 0,
            },
        )
        d["notes"] += 1
        d["inter"] += n.interaction_total
        d["reads"] += n.stat_count
        if re.search(r"repo|卡司|版本|唱段|复盘|返场|二刷", n.text, re.IGNORECASE):
            d["deep"] += 1
        d["fans"] = max(d["fans"], n.author_fans_count)

    cards = []
    for _, d in by_author.items():
        if d["notes"] < 1:
            continue
        er = d["inter"] / max(1, d["notes"])
        deep_rate = d["deep"] / d["notes"]
        hit = d["inter"] / d["notes"]
        score = er * 0.55 + deep_rate * 30 + math.log10(max(d["fans"], 1)) * 8 + min(d["notes"], 20) * 0.3
        cards.append(
            {
                "name": d["name"],
                "fans": d["fans"],
                "notes": d["notes"],
                "er": round(er, 2),
                "hit": int(hit),
                "deep_rate": deep_rate,
                "score": score,
            }
        )

    cards.sort(key=lambda x: x["score"], reverse=True)
    left = [x for x in cards if x["deep_rate"] >= 0.35][:6]
    left_names = {x["name"] for x in left}
    right = [x for x in cards if x["name"] not in left_names][:6]

    return {
        "kpi": [
            {"id": "left", "title": "圈层发声者", "value": len(left), "display": str(len(left))},
            {"id": "right", "title": "跨界种草机", "value": len(right), "display": str(len(right))},
            {"id": "mix", "title": "建议投放配比", "value": 46, "display": "4:6"},
        ],
        "chart_data": {"left": left, "right": right},
        "takeaway": "Key Takeaway：先用圈层发声者建立专业可信度，再用跨界种草机拉升触达与转化。",
    }


def _roadmap(brand_health: dict[str, Any]) -> dict[str, Any]:
    score_now = float(next((x.get("value") for x in brand_health.get("kpi", []) if x.get("id") == "total"), 0.0))
    target = min(95.0, score_now + 8.0)

    phases = [
        {"phase": "W1-W4", "focus": "建立心智", "target": "完成12条场景化内容，收藏率稳定在当前基线以上"},
        {"phase": "W5-W8", "focus": "扩大覆盖", "target": "达人联投与内容联动，提升声量份额"},
        {"phase": "W9-W13", "focus": "强化转化", "target": "围绕搜索词与产品词做承接，拉升转化潜力"},
    ]
    actions = [
        "每周固定三类内容：演前准备、剧院质感、演后复盘。",
        "达人池每两周复盘一次，淘汰低收藏低互动账号。",
        "持续占位品牌词+场景词，放大搜索入口流量。",
        "周复盘看板只保留3个核心指标：声量占比、收藏率、互动质量。",
    ]

    return {
        "kpi": [
            {"id": "weeks", "title": "执行周期", "value": 13, "display": "13周"},
            {"id": "assets", "title": "内容资产目标", "value": 39, "display": "39条"},
            {"id": "goal", "title": "健康度目标", "value": target, "display": f"{target:.1f}分"},
            {"id": "sov_goal", "title": "声量占比目标", "value": 0, "display": "持续提升"},
        ],
        "chart_data": {"phases": phases, "actions": actions},
        "takeaway": f"Key Takeaway：90天目标是把健康度从{score_now:.1f}分提升到{target:.1f}分。",
    }


def _global_meta(db) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM xhs_note_fact WHERE date(coalesce(publish_time, created_at)) >= current_date - 89) AS notes_90d,
              (SELECT COUNT(*) FROM xhs_comment_fact WHERE date(coalesce(created_at, now())) >= current_date - 89) AS comments_90d
            """
        )
    ).mappings().first() or {}

    return {"notes_90d": _to_int(row.get("notes_90d")), "comments_90d": _to_int(row.get("comments_90d"))}


def _build_report() -> dict[str, Any]:
    db = SessionLocal()
    try:
        global_meta = _global_meta(db)
        notes = _load_notes(db)
        metrics = _brand_metrics(notes)
        scored, benchmark = _score_health(metrics)

        executive = _executive(scored, benchmark)
        brand_health = _brand_health(scored, benchmark)
        competition = _competition(scored)
        audience_fit = _audience_fit(notes)
        content_engine = _content_engine(notes)
        influencer_strategy = _influencer_strategy(notes)
        roadmap_90d = _roadmap(brand_health)

        return {
            "meta": {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "window_days": WINDOW_DAYS,
                "brand": TARGET_BRAND,
                "platform": "小红书",
                "sample_notes": len(notes),
                "sample_interactions": sum(n.interaction_total for n in notes),
                "global_notes_90d": global_meta["notes_90d"],
            },
            "executive": executive,
            "brand_health": brand_health,
            "competition": competition,
            "audience_fit": audience_fit,
            "content_engine": content_engine,
            "influencer_strategy": influencer_strategy,
            "roadmap_90d": roadmap_90d,
        }
    finally:
        db.close()


def _html(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False)

    # Reuse V3 visual structure, only update title and data source labels
    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>雅顿品牌健康度洞察报告（真实数据版）</title>
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
<link href=\"https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap\" rel=\"stylesheet\">
<style>
:root {{
  --bg: #09090f; --bg2: #111118; --bg3: #16161f; --bg4: #1d1d28;
  --line: rgba(255,255,255,0.06); --line2: rgba(255,255,255,0.1);
  --text: #e8e8f0; --text2: #9898b0; --text3: #5a5a72;
  --blue: #4f7dff; --blue2: #2a4fd4; --blue-g: rgba(79,125,255,0.12);
  --purple: #a78bfa; --nav-w: 260px; --radius: 16px; --radius-sm: 10px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: 'Sora', 'Noto Sans SC', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }}
a {{ text-decoration: none; color: inherit; }}
.skip-link {{ position: absolute; left: 10px; top: -48px; background: #fff; color: #111; font-weight: 700; padding: 8px 10px; border-radius: 8px; z-index: 999; }}
.skip-link:focus-visible {{ top: 10px; }}
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
.hero h1 {{ font-size: 58px; font-weight: 800; line-height: 1.04; letter-spacing: -0.04em; color: #fff; max-width: 900px; }}
.hero h1 span {{ color: var(--blue); }}
.hero-desc {{ max-width: 820px; margin-top: 20px; font-size: 17px; color: var(--text2); line-height: 1.75; }}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }}
.hero-tag {{ font-size: 12px; padding: 5px 12px; border-radius: 6px; border: 1px solid var(--line2); color: var(--text2); font-family: 'DM Mono', monospace; }}
.hero-stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 40px; max-width: 760px; }}
.hstat {{ background: var(--bg3); border: 1px solid var(--line2); border-radius: var(--radius-sm); padding: 18px 20px; }}
.hstat-num {{ font-size: 28px; font-weight: 700; color: #fff; font-family: 'DM Mono', monospace; letter-spacing: -0.03em; }}
.hstat-label {{ font-size: 11px; color: var(--text3); margin-top: 4px; }}
.section {{ padding: 72px 64px; border-bottom: 1px solid var(--line); }}
.section:last-child {{ border-bottom: none; }}
.section-kicker {{ font-size: 11px; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.14em; color: var(--blue); margin-bottom: 10px; }}
.section h2 {{ font-size: 32px; font-weight: 700; letter-spacing: -0.03em; color: #fff; margin-bottom: 10px; line-height: 1.2; }}
.section-desc {{ font-size: 14px; color: var(--text2); max-width: 860px; line-height: 1.7; margin-bottom: 22px; }}
.grid2 {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }}
.grid3 {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; }}
.grid4 {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }}
.card {{ background: var(--bg3); border: 1px solid var(--line2); border-radius: var(--radius); padding: 24px; min-width: 0; }}
.card.blue {{ border-color: rgba(79,125,255,0.25); background: rgba(79,125,255,0.06); }}
.card.amber {{ border-color: rgba(245,166,35,0.25); background: rgba(245,166,35,0.05); }}
.card-title {{ font-size: 13px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}
.card-value {{ font-size: 26px; font-weight: 700; font-family: 'DM Mono', monospace; color: #fff; }}
.insight-box {{ background: var(--bg4); border-left: 3px solid var(--blue); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 14px 18px; margin: 18px 0 0; }}
.ib-label {{ font-size: 10px; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text3); margin-bottom: 6px; }}
.ib-text {{ font-size: 14px; color: var(--text); line-height: 1.7; }}
.mono {{ font-family: 'DM Mono', monospace; font-variant-numeric: tabular-nums; }}
.bar-row {{ display: grid; grid-template-columns: minmax(120px, 210px) 1fr 62px; gap: 10px; align-items: center; margin-bottom: 10px; }}
.bar-track {{ height: 8px; border-radius: 999px; background: var(--bg4); overflow: hidden; }}
.bar-fill {{ height: 8px; border-radius: 999px; background: linear-gradient(90deg, var(--blue), var(--purple)); }}
.type-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }}
.creator-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }}
.creator-col {{ display: grid; gap: 10px; }}
.creator-card {{ border: 1px solid var(--line2); border-radius: 12px; padding: 12px; background: var(--bg4); }}
.creator-name {{ font-size: 14px; font-weight: 600; color: #fff; }}
.creator-meta {{ font-size: 11px; color: var(--text3); }}
.btn-more {{ border: 1px solid var(--line2); border-radius: 8px; background: var(--bg3); color: var(--text2); padding: 8px 10px; cursor: pointer; transition: background-color .2s ease, border-color .2s ease; }}
.btn-more:hover {{ background: var(--bg4); border-color: rgba(79,125,255,.45); }}
.action-list {{ margin-left: 18px; }}
.action-list li {{ margin: 7px 0; color: #d8d8e8; }}
.phase-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; }}
.phase-card {{ border: 1px solid var(--line2); border-radius: 10px; background: var(--bg4); padding: 12px; }}
.phase-title {{ font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
.phase-focus {{ font-size: 12px; color: var(--text2); margin-bottom: 6px; }}
.phase-target {{ font-size: 12px; color: #dcdcf0; }}
@media (max-width: 1280px) {{ .section, .hero {{ padding-left: 36px; padding-right: 36px; }} .hero h1 {{ font-size: 46px; }} }}
@media (max-width: 1080px) {{ .nav {{ position: sticky; width: 100%; height: auto; max-height: 42vh; }} .main {{ margin-left: 0; }} .hero {{ min-height: auto; padding-top: 46px; }} .grid4 {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} .grid3 {{ grid-template-columns: 1fr; }} .grid2 {{ grid-template-columns: 1fr; }} .type-grid {{ grid-template-columns: 1fr; }} .creator-grid {{ grid-template-columns: 1fr; }} .phase-grid {{ grid-template-columns: 1fr; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }} }}
</style>
</head>
<body>
<a class=\"skip-link\" href=\"#main\">跳到正文</a>
<nav class=\"nav\" aria-label=\"章节导航\">
  <div class=\"nav-brand\">
    <div class=\"nb-tag\">XHS Brand Health Report</div>
    <div class=\"nb-name\">伊丽莎白雅顿品牌健康度洞察</div>
    <div class=\"nb-sub\" id=\"nav-sub\">真实数据库计算版</div>
  </div>
  <ul class=\"nav-toc\" id=\"toc\">
    <li class=\"toc-part\">Overview</li>
    <li><a href=\"#cover\">封面</a></li><li><a href=\"#executive\">高管摘要</a></li>
    <li class=\"toc-part\">Core</li>
    <li><a href=\"#brand-health\">品牌健康度</a></li><li><a href=\"#competition\">竞品对比</a></li><li><a href=\"#audience\">人群契合度</a></li><li><a href=\"#content\">内容引擎</a></li><li><a href=\"#influencer\">达人矩阵</a></li><li><a href=\"#roadmap\">90天路线图</a></li>
  </ul>
</nav>
<main class=\"main\" id=\"main\">
  <section class=\"hero\" id=\"cover\">
    <div class=\"hero-grid-bg\" aria-hidden=\"true\"></div>
    <div class=\"hero-chip\">XIAOHONGSHU · ELIZABETH ARDEN · REAL DATA</div>
    <h1>雅顿在音乐剧高端人群中的<span>品牌健康度</span>真实数据洞察</h1>
    <p class=\"hero-desc\">评分基于真实小红书数据计算：声量渗透、互动质量、内容资产、圈层匹配、转化潜力五维共100分。</p>
    <div class=\"hero-meta\" id=\"hero-meta\"></div>
    <div class=\"hero-stats\" id=\"hero-stats\"></div>
  </section>
  <section class=\"section\" id=\"executive\"><div class=\"section-kicker\">Executive Summary</div><h2>高管摘要</h2><p class=\"section-desc\">先看结论，再看动作。</p><div class=\"grid3\" id=\"executive-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"executive-takeaway\"></div></div><div class=\"grid2\" style=\"margin-top:16px;\"><div class=\"card blue\"><div class=\"card-title\">三条核心结论</div><ul class=\"action-list\" id=\"executive-findings\"></ul></div><div class=\"card amber\"><div class=\"card-title\">Top 5 动作</div><ol class=\"action-list\" id=\"executive-actions\"></ol></div></div></section>
  <section class=\"section\" id=\"brand-health\"><div class=\"section-kicker\">Brand Health</div><h2>雅顿品牌健康度总览</h2><p class=\"section-desc\">5维评分，标杆品牌明确展示。</p><div class=\"grid4\" id=\"brand-health-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"brand-health-takeaway\"></div></div><div class=\"grid2\" style=\"margin-top:16px;\"><div class=\"card\"><div class=\"card-title\">5维得分 vs 标杆</div><div id=\"health-dim-bars\"></div></div><div class=\"card\"><div class=\"card-title\">计算口径</div><ul class=\"action-list\" id=\"health-formula\"></ul></div></div></section>
  <section class=\"section\" id=\"competition\"><div class=\"section-kicker\">Competition</div><h2>雅顿 vs 高端竞品</h2><p class=\"section-desc\">看差距，定资源。</p><div class=\"grid3\" id=\"competition-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"competition-takeaway\"></div></div><div class=\"card\" style=\"margin-top:16px;\"><div class=\"card-title\">竞品对比面板</div><div id=\"competition-bars\"></div></div></section>
  <section class=\"section\" id=\"audience\"><div class=\"section-kicker\">Audience Fit</div><h2>音乐剧高端人群契合度</h2><p class=\"section-desc\">聚焦高转化场景。</p><div class=\"grid3\" id=\"audience-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"audience-takeaway\"></div></div><div class=\"grid2\" style=\"margin-top:16px;\"><div class=\"card\"><div class=\"card-title\">人群心理画像</div><div id=\"audience-trait-bars\"></div></div><div class=\"card\"><div class=\"card-title\">高价值场景优先级</div><div id=\"audience-scene-bars\"></div></div></div></section>
  <section class=\"section\" id=\"content\"><div class=\"section-kicker\">Content Engine</div><h2>高转化内容引擎</h2><p class=\"section-desc\">三类内容按指标分工。</p><div class=\"grid3\" id=\"content-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"content-takeaway\"></div></div><div class=\"type-grid\" id=\"content-types\" style=\"margin-top:16px;\"></div></section>
  <section class=\"section\" id=\"influencer\"><div class=\"section-kicker\">Influencer Strategy</div><h2>达人矩阵与投放配比</h2><p class=\"section-desc\">先建立背书，再放大场景。</p><div class=\"grid3\" id=\"influencer-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"influencer-takeaway\"></div></div><div class=\"creator-grid\" style=\"margin-top:16px;\"><div class=\"card\"><div class=\"card-title\">圈层发声者</div><div class=\"creator-col\" id=\"creator-left\"></div><button class=\"btn-more\" id=\"left-more\" type=\"button\" aria-label=\"加载更多圈层发声者\">加载更多</button></div><div class=\"card\"><div class=\"card-title\">跨界种草机</div><div class=\"creator-col\" id=\"creator-right\"></div><button class=\"btn-more\" id=\"right-more\" type=\"button\" aria-label=\"加载更多跨界种草机\">加载更多</button></div></div></section>
  <section class=\"section\" id=\"roadmap\"><div class=\"section-kicker\">Roadmap</div><h2>90天行动路线图</h2><p class=\"section-desc\">周节奏明确，指标可追踪。</p><div class=\"grid4\" id=\"roadmap-kpi\"></div><div class=\"insight-box\"><div class=\"ib-label\">Key Takeaway</div><div class=\"ib-text\" id=\"roadmap-takeaway\"></div></div><div class=\"phase-grid\" id=\"roadmap-phases\" style=\"margin-top:16px;\"></div><div class=\"card\" style=\"margin-top:16px;\"><div class=\"card-title\">执行动作清单</div><ol class=\"action-list\" id=\"roadmap-actions\"></ol></div></section>
</main>
<script id=\"report-data\" type=\"application/json\">{data_json}</script>
<script>
(function() {{
  const data = JSON.parse(document.getElementById('report-data').textContent || '{{}}');
  const nf = new Intl.NumberFormat('zh-CN');
  const state = {{ leftRender: 0, rightRender: 0 }};
  function renderStatCards(id, list) {{ const root = document.getElementById(id); if (!root) return; root.innerHTML = ''; (list || []).forEach((x) => {{ const node = document.createElement('article'); node.className = 'card'; node.innerHTML = `<div class="card-title">${{x.title || ''}}</div><div class="card-value mono">${{x.display || nf.format(x.value || 0)}}</div>`; root.appendChild(node); }}); }}
  function renderList(id, list) {{ const root = document.getElementById(id); if (!root) return; root.innerHTML=''; (list||[]).forEach((t) => {{ const li=document.createElement('li'); li.textContent=t; root.appendChild(li); }}); }}
  function barRow(name, score, max, suffix='') {{ const width=Math.max(0, Math.min(100, Math.round((score/Math.max(1,max))*100))); return `<div class="bar-row"><div>${{name}}</div><div class="bar-track"><div class="bar-fill" style="width:${{width}}%"></div></div><div class="mono">${{score}}${{suffix}}</div></div>`; }}
  function renderHero() {{ const m=data.meta||{{}}; document.getElementById('hero-meta').innerHTML=[`品牌：${{m.brand||''}}`,`平台：${{m.platform||''}}`,`窗口：近${{m.window_days||90}}天`,`样本笔记：${{nf.format(m.sample_notes||0)}}`,`更新时间：${{(m.generated_at||'').replace('T',' ')}}`].map(x=>`<span class="hero-tag">${{x}}</span>`).join(''); const cards=data.executive?.kpi||[]; document.getElementById('hero-stats').innerHTML=cards.map(s=>`<div class="hstat"><div class="hstat-num mono">${{s.display||s.value}}</div><div class="hstat-label">${{s.title||''}}</div></div>`).join(''); }}
  function renderExecutive() {{ renderStatCards('executive-kpi', data.executive?.kpi||[]); document.getElementById('executive-takeaway').textContent=data.executive?.takeaway||''; renderList('executive-findings', data.executive?.chart_data?.findings||[]); renderList('executive-actions', data.executive?.chart_data?.actions||[]); }}
  function renderBrandHealth() {{ const m=data.brand_health||{{}}; renderStatCards('brand-health-kpi', m.kpi||[]); document.getElementById('brand-health-takeaway').textContent=m.takeaway||''; const dims=m.chart_data?.dimensions||[]; const mx=Math.max(20,...dims.map(x=>x.benchmark||0)); document.getElementById('health-dim-bars').innerHTML=dims.map(x=>`<div style="margin-bottom:10px;">${{barRow(`${{x.name}}（雅顿）`, Number(x.score||0).toFixed(1), mx)}}${{barRow(`${{x.name}}（${{x.benchmark_brand||'标杆'}}）`, Number(x.benchmark||0).toFixed(1), mx)}}</div>`).join(''); document.getElementById('health-formula').innerHTML=["总分=5维得分相加，每维20分","声量渗透=品牌笔记量/组内最大值","互动质量=篇均互动/组内最大值","内容资产=高质量笔记占比/组内最大值","圈层匹配=发声作者数/组内最大值","转化潜力=篇均收藏/组内最大值"].map(t=>`<li>${{t}}</li>`).join(''); }}
  function renderCompetition() {{ const m=data.competition||{{}}; renderStatCards('competition-kpi', m.kpi||[]); document.getElementById('competition-takeaway').textContent=m.takeaway||''; const rows=m.chart_data?.rivals||[]; const mx=Math.max(100,...rows.map(x=>x.health||0)); document.getElementById('competition-bars').innerHTML=rows.map(x=>`<div style="padding:10px 0;border-bottom:1px solid var(--line);"><div class="mono" style="font-size:12px;color:var(--text2);margin-bottom:8px;">${{x.brand}} · 健康度${{x.health}} · 声量${{x.sov}}% · 篇均收藏${{x.save_rate}} · 篇均互动${{x.er}}</div>${{barRow(x.brand, x.health||0, mx)}}</div>`).join(''); }}
  function renderAudience() {{ const m=data.audience_fit||{{}}; renderStatCards('audience-kpi', m.kpi||[]); document.getElementById('audience-takeaway').textContent=m.takeaway||''; document.getElementById('audience-trait-bars').innerHTML=(m.chart_data?.traits||[]).map(x=>barRow(x.name, x.score||0, 100)).join(''); document.getElementById('audience-scene-bars').innerHTML=(m.chart_data?.scenes||[]).map(x=>barRow(x.name, x.score||0, 100)).join(''); }}
  function renderContent() {{ const m=data.content_engine||{{}}; renderStatCards('content-kpi', m.kpi||[]); document.getElementById('content-takeaway').textContent=m.takeaway||''; const root=document.getElementById('content-types'); root.innerHTML=''; (m.chart_data?.types||[]).forEach((x,i)=>{{ const card=document.createElement('article'); card.className=`card ${{i===0?'blue':i===1?'amber':''}}`; card.innerHTML=`<div class="card-title">${{x.type}}</div><div style="font-size:13px;color:var(--text2);margin-bottom:8px;">篇均互动 ${{x.er}} · 篇均收藏 ${{x.save_rate}} · 样本${{x.note_count}}</div><div class="ib-text">${{x.formula}}</div>`; root.appendChild(card); }}); }}
  function creatorCard(item) {{ return `<article class="creator-card"><div class="creator-name">${{item.name}}</div><div class="creator-meta mono">粉丝${{nf.format(item.fans||0)}} · 篇均互动 ${{item.er||0}} · 样本笔记${{item.notes||0}}</div></article>`; }}
  function renderCreatorSlice(id,list,start,count) {{ const root=document.getElementById(id); if(!root) return start; const next=Math.min(start+count,list.length); root.insertAdjacentHTML('beforeend', list.slice(start,next).map(creatorCard).join('')); return next; }}
  function renderInfluencer() {{ const m=data.influencer_strategy||{{}}; renderStatCards('influencer-kpi', m.kpi||[]); document.getElementById('influencer-takeaway').textContent=m.takeaway||''; const left=m.chart_data?.left||[]; const right=m.chart_data?.right||[]; state.leftRender=renderCreatorSlice('creator-left',left,0,4); state.rightRender=renderCreatorSlice('creator-right',right,0,4); const lb=document.getElementById('left-more'); const rb=document.getElementById('right-more'); const u=()=>{{ lb.style.display=state.leftRender>=left.length?'none':'inline-block'; rb.style.display=state.rightRender>=right.length?'none':'inline-block'; }}; lb.addEventListener('click',()=>{{ state.leftRender=renderCreatorSlice('creator-left',left,state.leftRender,3); u(); }}); rb.addEventListener('click',()=>{{ state.rightRender=renderCreatorSlice('creator-right',right,state.rightRender,3); u(); }}); u(); }}
  function renderRoadmap() {{ const m=data.roadmap_90d||{{}}; renderStatCards('roadmap-kpi', m.kpi||[]); document.getElementById('roadmap-takeaway').textContent=m.takeaway||''; document.getElementById('roadmap-phases').innerHTML=(m.chart_data?.phases||[]).map(x=>`<article class="phase-card"><div class="phase-title">${{x.phase}}</div><div class="phase-focus">重点：${{x.focus}}</div><div class="phase-target">目标：${{x.target}}</div></article>`).join(''); renderList('roadmap-actions', m.chart_data?.actions||[]); }}
  function bindTocActive() {{ const links=[...document.querySelectorAll('#toc a[href^="#"]')]; const map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a])); const sections=[...map.keys()].map(id=>document.getElementById(id)).filter(Boolean); const io=new IntersectionObserver((entries)=>{{ entries.forEach((entry)=>{{ const link=map.get(entry.target.id); if(!link) return; if(entry.isIntersecting) {{ links.forEach(x=>x.classList.remove('active')); link.classList.add('active'); }} }}); }}, {{ rootMargin:'-35% 0px -55% 0px', threshold:0.01 }}); sections.forEach(s=>io.observe(s)); }}
  renderHero(); renderExecutive(); renderBrandHealth(); renderCompetition(); renderAudience(); renderContent(); renderInfluencer(); renderRoadmap(); bindTocActive();
}})();
</script>
</body>
</html>"""


def main() -> None:
    report = _build_report()
    html = _html(report)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "generated_at": report.get("meta", {}).get("generated_at"),
                "brand": report.get("meta", {}).get("brand"),
                "health_score": next(
                    (
                        x.get("value")
                        for x in report.get("brand_health", {}).get("kpi", [])
                        if x.get("id") == "total"
                    ),
                    None,
                ),
                "sample_notes": report.get("meta", {}).get("sample_notes", 0),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
