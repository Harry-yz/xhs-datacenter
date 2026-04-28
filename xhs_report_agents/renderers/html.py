from __future__ import annotations

import html
import json
from typing import Any

from ..report_data import ReportDataComposer
from ..schemas import (
    AudienceInsights,
    ContentInsights,
    Diagnosis,
    EvidencePack,
    ExecutiveEditorial,
    FactCheckResult,
    MetricAnalysis,
    ReportBundle,
)


class PremiumHtmlRenderer:
    def render(self, bundle: ReportBundle) -> str:
        report_json = bundle.report_json or ReportDataComposer().compose(
            evidence=bundle.evidence_pack,
            metric=bundle.metric_analysis,
            content=bundle.content_insights,
            audience=bundle.audience_insights,
            diagnosis=bundle.diagnosis,
            fact_check=bundle.fact_check,
            executive=bundle.executive_editorial,
        )
        return self.render_report(report_json)

    def render_report(self, report: dict[str, Any]) -> str:
        meta = report.get("meta", {})
        kpis = report.get("kpis", {})
        editorial = report.get("editorial", {})
        brand = str(meta.get("brand") or "品牌")
        title = str(editorial.get("title") or f"{brand} 小红书品牌健康报告")
        subtitle = str(editorial.get("subtitle") or f"近 {meta.get('window_days', 90)} 天全量相关数据聚合")
        data_json = json.dumps(report, ensure_ascii=False, default=str)
        sections = report.get("report_sections") or []
        nav = [(item.get("section_id") or f"section-{idx:02d}", item.get("title") or f"章节 {idx}") for idx, item in enumerate(sections, start=1)]
        if not nav:
            nav = [
                ("overview", "总览"),
                ("score", "健康评分"),
                ("competition", "竞品格局"),
                ("content", "内容洞察"),
                ("audience", "受众洞察"),
                ("actions", "行动计划"),
            ]
        section_html = "".join(_report_section(item, idx) for idx, item in enumerate(sections, start=1))
        if not section_html:
            section_html = (
                _overview_section(report)
                + _score_section(report)
                + _competition_section(report)
                + _content_section(report)
                + _audience_section(report)
                + _actions_section(report)
            )
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_e(title)}</title>
<style>
:root {{
  --bg:#f7f0e8; --paper:#fffdf9; --card:#ffffff; --ink:#25211d; --muted:#746b61;
  --line:#eaded2; --soft:#fbf6ef; --accent:#d96d45; --accent-2:#9c6f4b; --sage:#7f9a83;
  --rose:#d98d8b; --gold:#c9a24f; --shadow:0 24px 80px rgba(78,52,31,.12);
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{
  margin:0; color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC","PingFang SC",sans-serif;
  background:
    radial-gradient(circle at 16% 8%, rgba(217,109,69,.18), transparent 30%),
    linear-gradient(135deg,#f8efe5 0%,#fffaf4 42%,#f2eadf 100%);
}}
.shell {{ width:min(1600px, calc(100% - 44px)); margin:0 auto; padding:28px 0 64px; display:grid; grid-template-columns:292px minmax(0,1fr); gap:26px; }}
.side {{ position:sticky; top:24px; align-self:start; max-height:calc(100vh - 48px); overflow:auto; padding:24px; border:1px solid rgba(234,222,210,.9); border-radius:30px; background:rgba(255,253,249,.84); box-shadow:var(--shadow); backdrop-filter:blur(18px); scrollbar-width:thin; scrollbar-color:rgba(217,109,69,.46) rgba(255,246,236,.62); }}
.side::-webkit-scrollbar {{ width:8px; }}
.side::-webkit-scrollbar-track {{ background:rgba(255,246,236,.72); border-radius:999px; margin:18px 0; }}
.side::-webkit-scrollbar-thumb {{ background:linear-gradient(180deg,rgba(217,109,69,.62),rgba(201,162,79,.58)); border-radius:999px; border:2px solid rgba(255,253,249,.92); }}
.side::-webkit-scrollbar-thumb:hover {{ background:linear-gradient(180deg,rgba(217,109,69,.82),rgba(156,111,75,.72)); }}
.mark {{ font-size:13px; color:var(--accent); font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
.side h1 {{ margin:10px 0 8px; font-size:25px; line-height:1.16; letter-spacing:0; }}
.side p {{ margin:0 0 18px; color:var(--muted); line-height:1.65; font-size:13px; }}
.nav {{ display:grid; gap:8px; margin-top:18px; }}
.nav a {{ color:#44372d; text-decoration:none; border:1px solid transparent; border-radius:999px; padding:10px 13px; font-size:14px; }}
.nav a:hover {{ background:#fff6ec; border-color:#efd8c7; color:#a74e2e; }}
.main {{ display:grid; gap:22px; min-width:0; }}
.hero,.section {{ background:rgba(255,253,249,.93); border:1px solid rgba(234,222,210,.92); border-radius:34px; box-shadow:var(--shadow); }}
.hero {{ min-height:430px; padding:42px; display:grid; align-content:space-between; overflow:hidden; position:relative; }}
.hero:after {{ content:""; position:absolute; right:36px; top:36px; width:220px; height:220px; border-radius:50%; background:conic-gradient(from 160deg,var(--accent),var(--gold),var(--sage),var(--rose),var(--accent)); opacity:.18; filter:blur(.2px); }}
.hero-content {{ position:relative; z-index:1; max-width:900px; }}
.eyebrow {{ display:inline-flex; gap:8px; align-items:center; color:#8a5338; font-size:13px; font-weight:800; padding:7px 12px; border:1px solid #efd8c7; border-radius:999px; background:#fff6ec; }}
.hero h2 {{ margin:22px 0 14px; font-size:clamp(40px,5vw,74px); line-height:.98; letter-spacing:0; }}
.hero .sub {{ margin:0; max-width:780px; color:#655d55; font-size:18px; line-height:1.72; }}
.kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; position:relative; z-index:1; }}
.kpi {{ background:linear-gradient(180deg,#fff,#fff8f0); border:1px solid #eadbcf; border-radius:24px; padding:18px; min-height:116px; }}
.kpi span {{ display:block; color:#857a70; font-size:13px; margin-bottom:12px; }}
.kpi strong {{ display:block; font-size:30px; line-height:1; }}
.kpi em {{ display:block; margin-top:10px; color:#9a6b4f; font-size:12px; font-style:normal; }}
.section {{ padding:30px; }}
.section-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:18px; margin-bottom:20px; }}
.section h3 {{ margin:0; font-size:30px; line-height:1.1; letter-spacing:0; }}
.section-copy {{ margin:8px 0 0; color:var(--muted); line-height:1.7; max-width:820px; }}
.grid-2 {{ display:grid; grid-template-columns:1.08fr .92fr; gap:18px; }}
.grid-3 {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:24px; padding:20px; min-width:0; }}
.panel h4 {{ margin:0 0 14px; font-size:18px; }}
.finding {{ display:grid; gap:12px; margin:0; padding:0; list-style:none; }}
.finding li {{ padding:14px 15px; border-radius:18px; background:#fbf6ef; border:1px solid #efe4d8; line-height:1.65; }}
.bars {{ display:grid; gap:12px; }}
.bar-row {{ display:grid; grid-template-columns:112px minmax(0,1fr) 48px; gap:10px; align-items:center; font-size:13px; }}
.track {{ height:10px; border-radius:999px; background:#f1e6db; overflow:hidden; }}
.fill {{ height:100%; border-radius:999px; background:linear-gradient(90deg,var(--accent),var(--gold)); }}
.radar-wrap {{ display:grid; place-items:center; min-height:310px; }}
.radar-label {{ fill:#6d6258; font-size:11px; }}
.table {{ width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; border:1px solid var(--line); border-radius:18px; }}
.table th,.table td {{ padding:13px 14px; text-align:left; border-bottom:1px solid var(--line); font-size:14px; }}
.table th {{ background:#fbf3ea; color:#6a5544; font-weight:800; }}
.table tr:last-child td {{ border-bottom:0; }}
.chips {{ display:flex; flex-wrap:wrap; gap:10px; }}
.chip {{ display:inline-flex; gap:8px; align-items:center; padding:9px 12px; background:#fff7ef; border:1px solid #ecd9ca; border-radius:999px; font-size:13px; color:#5b4d42; }}
.note-list {{ display:grid; gap:12px; }}
.note {{ padding:15px; border:1px solid var(--line); border-radius:20px; background:#fff; }}
.note-title {{ font-weight:800; margin-bottom:8px; line-height:1.45; }}
.note-meta {{ color:var(--muted); font-size:12px; }}
.target {{ display:grid; grid-template-columns:40px minmax(0,1fr); gap:12px; align-items:start; padding:14px; border-radius:20px; background:#fffaf4; border:1px solid #ecdccd; }}
.num {{ width:34px; height:34px; display:grid; place-items:center; border-radius:50%; background:#d96d45; color:white; font-weight:900; }}
.chart-grid {{ display:grid; grid-template-columns:1.1fr .9fr; gap:18px; }}
.chart-box {{ min-height:300px; display:grid; align-content:center; }}
.axis-label {{ fill:#7b7067; font-size:11px; }}
.dot-label {{ fill:#4d4239; font-size:11px; font-weight:800; }}
.matrix {{ display:grid; gap:10px; }}
.matrix-row {{ display:grid; grid-template-columns:76px minmax(0,1fr) 48px; gap:10px; align-items:center; font-size:13px; }}
.pill {{ display:inline-flex; align-items:center; justify-content:center; padding:5px 8px; border-radius:999px; background:#fff6ec; border:1px solid #ecd9ca; color:#8a5338; font-size:12px; white-space:nowrap; }}
@media (max-width: 1080px) {{ .shell {{ grid-template-columns:1fr; }} .side {{ position:relative; top:auto; }} .kpis,.grid-3,.grid-2 {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width: 720px) {{ .shell {{ width:min(100% - 24px,1600px); padding-top:14px; }} .hero,.section {{ border-radius:24px; padding:22px; }} .kpis,.grid-3,.grid-2,.chart-grid {{ grid-template-columns:1fr; }} .hero h2 {{ font-size:38px; }} .bar-row {{ grid-template-columns:88px minmax(0,1fr) 42px; }} }}
</style>
</head>
<body>
<script id="report-data" type="application/json">{_e(data_json)}</script>
<div class="shell">
  <aside class="side">
    <div class="mark">XHS Brand Health</div>
    <h1>{_e(brand)}</h1>
    <p>{_e(subtitle)}<br/>生成时间：{_e(str(meta.get("generated_at") or ""))}</p>
    <nav class="nav">{''.join(f'<a href="#{sid}">{_e(label)}</a>' for sid, label in nav)}</nav>
  </aside>
  <main class="main">
    <section class="hero" id="overview">
      <div class="hero-content">
        <div class="eyebrow">全量聚合 · 抽样证据 · 事实校验</div>
        <h2>{_e(title)}</h2>
        <p class="sub">{_e(str(editorial.get("executive_summary") or ""))}</p>
      </div>
      <div class="kpis">
        {_kpi("健康度", _fmt(kpis.get("health_score")), "/100")}
        {_kpi("相关笔记", _fmt(kpis.get("note_count")), "全量聚合")}
        {_kpi("参与作者", _fmt(kpis.get("author_count")), "去重作者")}
        {_kpi("总互动", _fmt(kpis.get("interaction_total")), "赞评藏转")}
      </div>
    </section>
    {_visual_dashboard(report)}
    {section_html}
  </main>
</div>
</body>
</html>
"""


HtmlRenderer = PremiumHtmlRenderer


def _report_section(section: dict[str, Any], idx: int) -> str:
    section_id = section.get("section_id") or f"section-{idx:02d}"
    title = section.get("title") or f"报告章节 {idx}"
    eyebrow = section.get("eyebrow") or "XHS Brand Health"
    judgment = section.get("core_judgment") or ""
    evidence = section.get("evidence") or []
    body = section.get("body") or []
    bullets = section.get("bullets") or []
    table = section.get("table") or []
    cards = section.get("cards") or []
    return f"""
    <section class="section report-section" id="{_e(section_id)}">
      <div class="section-head">
        <div>
          <div class="eyebrow">{_e(eyebrow)}</div>
          <h3>{idx:02d} · {_e(title)}</h3>
          <p class="section-copy">{_e(judgment)}</p>
        </div>
      </div>
      <div class="grid-2">
        <div class="panel"><h4>数据证据</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in evidence[:6])}</ul></div>
        <div class="panel"><h4>关键要点</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in bullets[:6])}</ul></div>
      </div>
      <div class="panel" style="margin-top:18px">{''.join(f'<p class="section-copy">{_e(p)}</p>' for p in body[:4])}</div>
      {_table_panel(table)}
      {_cards_panel(cards)}
    </section>"""


def _table_panel(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return ""
    dict_rows = [row for row in rows if isinstance(row, dict)]
    if not dict_rows:
        return ""
    headers: list[str] = []
    for row in dict_rows:
        for key in row.keys():
            if str(key) not in headers:
                headers.append(str(key))
        if len(headers) >= 5:
            break
    headers = headers[:5]
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_e(row.get(h, ''))}</td>" for h in headers) + "</tr>" for row in dict_rows[:10])
    return f'<div class="panel" style="margin-top:18px"><h4>结构化证据</h4><table class="table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _cards_panel(cards: Any) -> str:
    if not isinstance(cards, list) or not cards:
        return ""
    items = []
    for card in cards[:6]:
        if not isinstance(card, dict):
            continue
        label = card.get("title") or card.get("label") or card.get("name") or "洞察"
        value = card.get("value") or card.get("description") or card.get("content") or ""
        items.append(f'<div class="kpi"><span>{_e(label)}</span><strong>{_e(value)}</strong></div>')
    return f'<div class="grid-3" style="margin-top:18px">{"".join(items)}</div>' if items else ""


def _overview_section(report: dict[str, Any]) -> str:
    editorial = report.get("editorial", {})
    findings = _as_list(editorial.get("key_findings")) or _claims(report.get("diagnosis", {}).get("executive_findings", []))
    kpis = report.get("kpis", {})
    return f"""
    <section class="section">
      <div class="section-head"><div><h3>管理层摘要</h3><p class="section-copy">{_e(str(editorial.get("management_diagnosis") or ""))}</p></div></div>
      <div class="grid-2">
        <div class="panel"><h4>关键发现</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in findings[:5])}</ul></div>
        <div class="panel"><h4>互动资产</h4><div class="grid-3">
          {_mini_metric("点赞", kpis.get("like_total"))}
          {_mini_metric("评论", kpis.get("comment_total"))}
          {_mini_metric("收藏", kpis.get("collection_total"))}
        </div></div>
      </div>
    </section>"""


def _score_section(report: dict[str, Any]) -> str:
    dimensions = report.get("dimension_scores", [])
    return f"""
    <section class="section" id="score">
      <div class="section-head"><div><h3>六维健康评分</h3><p class="section-copy">评分来自 Flash 分析节点，核心数字来自数据库全量相关笔记聚合；置信度随数据完整度调整。</p></div></div>
      <div class="grid-2">
        <div class="panel"><h4>评分雷达</h4><div class="radar-wrap">{_radar_svg(dimensions)}</div></div>
        <div class="panel"><h4>维度明细</h4><div class="bars">{''.join(_bar_row(d.get("name"), d.get("score"), d.get("confidence")) for d in dimensions)}</div></div>
      </div>
    </section>"""


def _competition_section(report: dict[str, Any]) -> str:
    competitors = report.get("competitors", [])
    rows = "".join(
        f"<tr><td>{_e(c.get('brand'))}</td><td>{_fmt(c.get('note_count'))}</td><td>{_fmt(c.get('author_count'))}</td><td>{_fmt(c.get('interaction_total'))}</td><td>{_fmt(c.get('avg_interaction'))}</td></tr>"
        for c in competitors
    ) or "<tr><td colspan='5'>暂无竞品数据</td></tr>"
    return f"""
    <section class="section" id="competition">
      <div class="section-head"><div><h3>竞品对比</h3><p class="section-copy">同一窗口、同一聚合口径下对比相关笔记、作者和互动效率。</p></div></div>
      <div class="panel"><table class="table"><thead><tr><th>品牌</th><th>笔记</th><th>作者</th><th>总互动</th><th>篇均互动</th></tr></thead><tbody>{rows}</tbody></table></div>
    </section>"""


def _content_section(report: dict[str, Any]) -> str:
    content = report.get("content", {})
    keywords = report.get("keywords", [])
    topics = report.get("topics", [])
    notes = report.get("top_notes", [])
    clusters = content.get("clusters", [])
    return f"""
    <section class="section" id="content">
      <div class="section-head"><div><h3>内容与搜索洞察</h3><p class="section-copy">关键词、主题和高表现笔记均来自结构化 report data，适合直接转成达人 brief 和选题池。</p></div></div>
      <div class="grid-2">
        <div class="panel"><h4>关键词分布</h4><div class="chips">{''.join(_keyword_chip(k) for k in keywords[:18])}</div></div>
        <div class="panel"><h4>内容主题</h4><div class="bars">{''.join(_cluster_row(c) for c in clusters[:8])}</div></div>
      </div>
      <div class="panel" style="margin-top:18px"><h4>高频标签主题</h4><div class="chips">{''.join(_topic_chip(t) for t in topics[:20])}</div></div>
      <div class="panel" style="margin-top:18px"><h4>代表性笔记</h4><div class="note-list">{''.join(_note_card(n) for n in notes[:8])}</div></div>
    </section>"""


def _audience_section(report: dict[str, Any]) -> str:
    audience = report.get("audience", {})
    segments = audience.get("segments", [])
    motivations = _claims(audience.get("purchase_motivations", []))
    pain_points = _claims(audience.get("pain_points", []))
    return f"""
    <section class="section" id="audience">
      <div class="section-head"><div><h3>受众洞察</h3><p class="section-copy">受众判断只基于当前数据库中的笔记文本、评论样本、作者与搜索词信号。</p></div></div>
      <div class="grid-3">
        <div class="panel"><h4>人群分层</h4><ul class="finding">{''.join(f'<li>{_e(_dict_title(x))}</li>' for x in segments[:5])}</ul></div>
        <div class="panel"><h4>购买动机</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in motivations[:5])}</ul></div>
        <div class="panel"><h4>痛点与顾虑</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in pain_points[:5])}</ul></div>
      </div>
    </section>"""


def _actions_section(report: dict[str, Any]) -> str:
    diagnosis = report.get("diagnosis", {})
    targets = _as_list(diagnosis.get("next_90_days_targets"))
    actions = _as_list(diagnosis.get("priority_actions"))
    items = targets or actions
    return f"""
    <section class="section" id="actions">
      <div class="section-head"><div><h3>90 天目标与动作</h3><p class="section-copy">把诊断结论收敛为可执行目标，便于后续按周复盘。</p></div></div>
      <div class="grid-2">
        <div class="panel"><h4>目标拆解</h4>{''.join(_target(i, x) for i, x in enumerate(items[:6], start=1))}</div>
        <div class="panel"><h4>优先动作</h4><ul class="finding">{''.join(f'<li>{_e(x)}</li>' for x in actions[:6])}</ul></div>
      </div>
    </section>"""


def _visual_dashboard(report: dict[str, Any]) -> str:
    chart_data = report.get("chart_data", {})
    weekly = chart_data.get("weekly_trend") or report.get("weekly_trend", [])
    competitors = chart_data.get("competitor_quadrant") or report.get("competitor_positioning", [])
    keyword_matrix = chart_data.get("keyword_matrix") or report.get("keyword_opportunity_matrix", [])
    confidence = chart_data.get("confidence_summary") or report.get("confidence_summary", {})
    if not any([weekly, competitors, keyword_matrix, confidence]):
        return ""
    return f"""
    <section class="section" id="charts">
      <div class="section-head"><div><h3>核心图表洞察</h3><p class="section-copy">把声量趋势、竞品相对位置、关键词机会和证据强弱压缩成可讨论的管理层视图。</p></div></div>
      <div class="chart-grid">
        <div class="panel chart-box"><h4>声量与互动趋势</h4>{_line_chart_svg(weekly)}</div>
        <div class="panel chart-box"><h4>竞品声量 / 效率象限</h4>{_quadrant_svg(competitors)}</div>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <div class="panel"><h4>关键词机会矩阵</h4>{_keyword_matrix(keyword_matrix)}</div>
        <div class="panel"><h4>证据置信度</h4>{_confidence_panel(confidence)}</div>
      </div>
    </section>"""


def _line_chart_svg(rows: list[dict[str, Any]]) -> str:
    points = rows[-14:]
    if not points:
        return '<p class="section-copy">暂无趋势数据。</p>'
    width, height = 620, 260
    pad_l, pad_r, pad_t, pad_b = 46, 18, 24, 38
    max_notes = max([_float(x.get("note_count")) for x in points] or [1]) or 1
    max_interactions = max([_float(x.get("interaction_total")) for x in points] or [1]) or 1
    usable_w = width - pad_l - pad_r
    usable_h = height - pad_t - pad_b
    def coords(key: str, max_value: float) -> list[tuple[float, float]]:
        out = []
        for idx, item in enumerate(points):
            x = pad_l + (usable_w * idx / max(len(points) - 1, 1))
            y = pad_t + usable_h - usable_h * (_float(item.get(key)) / max_value)
            out.append((x, y))
        return out
    note_points = coords("note_count", max_notes)
    interaction_points = coords("interaction_total", max_interactions)
    def path(items: list[tuple[float, float]]) -> str:
        return " ".join(("M" if idx == 0 else "L") + f"{x:.1f},{y:.1f}" for idx, (x, y) in enumerate(items))
    labels = "".join(
        f'<text class="axis-label" x="{x:.1f}" y="{height-12}" text-anchor="middle">{_e(str(points[idx].get("week_start", ""))[5:10])}</text>'
        for idx, (x, _) in enumerate(note_points)
        if idx in {0, len(note_points) - 1} or idx % 3 == 0
    )
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" height="260" role="img">
      <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#eaded2"/>
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#eaded2"/>
      <path d="{path(note_points)}" fill="none" stroke="#d96d45" stroke-width="4" stroke-linecap="round"/>
      <path d="{path(interaction_points)}" fill="none" stroke="#7f9a83" stroke-width="4" stroke-linecap="round" opacity=".88"/>
      {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#d96d45"/>' for x, y in note_points)}
      {labels}
      <text class="axis-label" x="{pad_l}" y="16">笔记</text><text class="axis-label" x="{width-74}" y="16">互动</text>
    </svg>"""


def _quadrant_svg(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="section-copy">暂无竞品象限数据。</p>'
    width, height = 520, 300
    pad = 44
    max_x = max([_float(x.get("volume_index")) for x in rows] + [140])
    max_y = max([_float(x.get("efficiency_index")) for x in rows] + [140])
    items = []
    for idx, item in enumerate(rows[:8]):
        x = pad + (width - pad * 2) * min(_float(item.get("volume_index")) / max_x, 1)
        y = height - pad - (height - pad * 2) * min(_float(item.get("efficiency_index")) / max_y, 1)
        color = "#d96d45" if idx == 0 else "#7f9a83"
        items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{color}" opacity=".92"/><text class="dot-label" x="{x+11:.1f}" y="{y+4:.1f}">{_e(item.get("brand"))}</text>')
    mid_x = pad + (width - pad * 2) * min(100 / max_x, 1)
    mid_y = height - pad - (height - pad * 2) * min(100 / max_y, 1)
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" height="300" role="img">
      <rect x="{pad}" y="{pad}" width="{width-pad*2}" height="{height-pad*2}" rx="18" fill="#fffaf4" stroke="#eaded2"/>
      <line x1="{mid_x:.1f}" y1="{pad}" x2="{mid_x:.1f}" y2="{height-pad}" stroke="#eaded2" stroke-dasharray="6 6"/>
      <line x1="{pad}" y1="{mid_y:.1f}" x2="{width-pad}" y2="{mid_y:.1f}" stroke="#eaded2" stroke-dasharray="6 6"/>
      <text class="axis-label" x="{width/2}" y="{height-10}" text-anchor="middle">声量指数</text>
      <text class="axis-label" x="14" y="{height/2}" transform="rotate(-90 14 {height/2})" text-anchor="middle">效率指数</text>
      {''.join(items)}
    </svg>"""


def _keyword_matrix(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="section-copy">暂无关键词机会数据。</p>'
    html_rows = []
    for item in rows[:8]:
        score = max(0, min(100, _float(item.get("opportunity_score"))))
        html_rows.append(
            f'<div class="matrix-row"><span class="pill">{_e(item.get("category"))}</span><div><div class="note-title">{_e(item.get("keyword"))}</div><div class="track"><div class="fill" style="width:{score:.1f}%"></div></div></div><strong>{score:.0f}</strong></div>'
        )
    return f'<div class="matrix">{"".join(html_rows)}</div>'


def _confidence_panel(summary: dict[str, Any]) -> str:
    counts = summary.get("counts") if isinstance(summary, dict) else {}
    high = int((counts or {}).get("high") or 0)
    medium = int((counts or {}).get("medium") or 0)
    low = int((counts or {}).get("low") or 0)
    total = max(high + medium + low, 1)
    rows = [("强证据", high, "#7f9a83"), ("趋势信号", medium, "#d96d45"), ("待验证", low, "#c9a24f")]
    return '<div class="bars">' + ''.join(
        f'<div class="bar-row"><span>{label}</span><div class="track"><div class="fill" style="width:{count/total*100:.1f}%; background:{color}"></div></div><strong>{count}</strong></div>'
        for label, count, color in rows
    ) + '</div>'


def _kpi(label: str, value: str, hint: str) -> str:
    return f'<div class="kpi"><span>{_e(label)}</span><strong>{_e(value)}</strong><em>{_e(hint)}</em></div>'


def _mini_metric(label: str, value: Any) -> str:
    return f'<div class="kpi"><span>{_e(label)}</span><strong>{_fmt(value)}</strong></div>'


def _bar_row(name: Any, score: Any, confidence: Any = "") -> str:
    num = max(0.0, min(100.0, _float(score)))
    return f'<div class="bar-row"><span>{_e(name)}</span><div class="track"><div class="fill" style="width:{num:.1f}%"></div></div><strong>{num:.0f}</strong></div>'


def _cluster_row(cluster: dict[str, Any]) -> str:
    name = cluster.get("name") or cluster.get("cluster") or cluster.get("theme") or "内容主题"
    score = cluster.get("share") or cluster.get("score") or cluster.get("note_count") or 48
    return _bar_row(name, score)


def _keyword_chip(item: dict[str, Any]) -> str:
    label = item.get("search_keyword") or item.get("keyword") or "未标注"
    count = item.get("note_count") or 0
    return f'<span class="chip">{_e(label)} <strong>{_fmt(count)}</strong></span>'


def _topic_chip(item: dict[str, Any]) -> str:
    label = item.get("name") or item.get("topic") or "主题"
    count = item.get("note_count") or 0
    return f'<span class="chip">{_e(label)} <strong>{_fmt(count)}</strong></span>'


def _note_card(note: dict[str, Any]) -> str:
    title = note.get("title") or note.get("content_excerpt") or "未命名笔记"
    meta = f"{note.get('author_nickname') or '未知作者'} · 互动 {_fmt(note.get('interaction_total'))} · 收藏 {_fmt(note.get('collection_count'))}"
    return f'<article class="note"><div class="note-title">{_e(title)}</div><div class="note-meta">{_e(meta)}</div></article>'


def _target(idx: int, text: str) -> str:
    return f'<div class="target"><div class="num">{idx}</div><div>{_e(text)}</div></div>'


def _radar_svg(dimensions: list[dict[str, Any]]) -> str:
    items = dimensions[:6] or [{"name": "数据", "score": 0}]
    size = 300
    center = size / 2
    radius = 104
    import math

    points = []
    labels = []
    axes = []
    for idx, item in enumerate(items):
        angle = -math.pi / 2 + idx * (2 * math.pi / len(items))
        score_radius = radius * max(0, min(100, _float(item.get("score")))) / 100
        points.append(f"{center + math.cos(angle) * score_radius:.1f},{center + math.sin(angle) * score_radius:.1f}")
        axes.append(f'<line x1="{center}" y1="{center}" x2="{center + math.cos(angle)*radius:.1f}" y2="{center + math.sin(angle)*radius:.1f}" stroke="#eaded2"/>')
        labels.append(f'<text class="radar-label" x="{center + math.cos(angle)*(radius+28):.1f}" y="{center + math.sin(angle)*(radius+28):.1f}" text-anchor="middle">{_e(item.get("name"))}</text>')
    rings = "".join(f'<circle cx="{center}" cy="{center}" r="{radius*i/4:.1f}" fill="none" stroke="#efe4d8"/>' for i in range(1, 5))
    return f'<svg viewBox="0 0 {size} {size}" width="100%" height="300" role="img">{rings}{"".join(axes)}<polygon points="{" ".join(points)}" fill="rgba(217,109,69,.28)" stroke="#d96d45" stroke-width="3"/>{"".join(labels)}</svg>'


def _claims(items: Any) -> list[str]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            text = item.get("claim") or item.get("description") or item.get("summary") or item.get("name")
        else:
            text = item
        if text:
            out.append(str(text))
    return out


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x.get("description") or x.get("claim") or x.get("name") or x) if isinstance(x, dict) else str(x) for x in value if x]
    return [str(value)]


def _dict_title(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("segment") or value.get("description") or value)
    return str(value)


def _fmt(value: Any) -> str:
    if value is None:
        return "0"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(num) >= 10000:
        return f"{num / 10000:.1f}万"
    if num.is_integer():
        return f"{int(num):,}"
    return f"{num:.1f}"


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)
