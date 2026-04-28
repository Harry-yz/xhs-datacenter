from __future__ import annotations

from typing import Any

from ..schemas import AudienceInsights, ContentInsights, Diagnosis, EvidencePack, FactCheckResult, MetricAnalysis


def render_report_markdown(report: dict[str, Any]) -> str:
    meta = report.get("meta", {})
    editorial = report.get("editorial", {})
    brand = meta.get("brand") or report.get("report_meta", {}).get("brand") or "品牌"
    title = editorial.get("title") or f"{brand} 小红书品牌健康报告"
    lines = [f"# {title}", ""]
    subtitle = editorial.get("subtitle")
    if subtitle:
        lines.extend([f"**{subtitle}**", ""])
    summary = editorial.get("executive_summary")
    if summary:
        lines.extend(["## 报告摘要", "", str(summary), ""])
    for section in report.get("report_sections", []):
        lines.extend(_section_to_markdown(section))
    return "\n".join(lines).strip() + "\n"


def _section_to_markdown(section: dict[str, Any]) -> list[str]:
    title = section.get("title") or "报告章节"
    out = [f"## {title}", ""]
    if section.get("core_judgment"):
        out.extend([f"**核心判断：** {section['core_judgment']}", ""])
    evidence = section.get("evidence") or []
    if evidence:
        out.append("**数据证据：**")
        out.extend(f"- {item}" for item in evidence if item)
        out.append("")
    for paragraph in section.get("body") or []:
        out.extend([str(paragraph), ""])
    bullets = section.get("bullets") or []
    if bullets:
        out.append("**关键要点：**")
        out.extend(f"- {item}" for item in bullets if item)
        out.append("")
    table = section.get("table") or []
    if table:
        out.extend(_table_to_markdown(table))
        out.append("")
    cards = section.get("cards") or []
    for card in cards:
        if isinstance(card, dict):
            label = card.get("title") or card.get("label") or card.get("name") or "卡片"
            value = card.get("value") or card.get("description") or card.get("content") or ""
            out.append(f"- **{label}**：{value}")
    if cards:
        out.append("")
    return out


def _table_to_markdown(rows: list[dict[str, Any]]) -> list[str]:
    dict_rows = [row for row in rows if isinstance(row, dict)]
    if not dict_rows:
        return []
    headers: list[str] = []
    for row in dict_rows:
        for key in row.keys():
            if str(key) not in headers:
                headers.append(str(key))
        if len(headers) >= 5:
            break
    headers = headers[:5]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in dict_rows[:10]:
        out.append("| " + " | ".join(str(row.get(key, "")) for key in headers) + " |")
    return out


def fallback_markdown(
    *,
    evidence: EvidencePack,
    metric: MetricAnalysis,
    content: ContentInsights,
    audience: AudienceInsights,
    diagnosis: Diagnosis,
    fact_check: FactCheckResult,
) -> str:
    m = evidence.core_metrics
    lines = [
        f"# {evidence.brand} 小红书品牌健康报告",
        "",
        f"生成时间：{evidence.generated_at}",
        f"分析窗口：近 {evidence.window_days} 天",
        "",
        "## 报告摘要",
        f"- 品牌健康度总分：{metric.overall_score:.1f}/100",
        f"- 样本笔记：{m.note_count} 条，作者：{m.author_count} 个，互动合计：{m.interaction_total}",
        f"- 数据质量：{evidence.data_quality.status}；{'; '.join(evidence.data_quality.reasons) or '无明显限制'}",
        "",
        "## 核心指标速览",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 笔记数 | {m.note_count} |",
        f"| 作者数 | {m.author_count} |",
        f"| 点赞 | {m.like_total} |",
        f"| 评论 | {m.comment_total} |",
        f"| 收藏 | {m.collection_total} |",
        f"| 分享 | {m.share_total} |",
        f"| 总互动 | {m.interaction_total} |",
        "",
        "## 关键发现",
    ]
    claims = fact_check.approved_claims or diagnosis.executive_findings or metric.metric_findings
    lines.extend([f"- {c.claim}" for c in claims[:6]] or ["- 暂无足够证据形成高置信度关键发现。"])
    lines.extend(["", "## 品牌健康度评分"])
    for item in metric.dimension_scores:
        lines.append(f"- **{item.name}**：{item.score:.1f}/100（{item.confidence}）- {item.rationale}")
    lines.extend(["", "## 内容与受众洞察"])
    lines.extend([f"- {c.claim}" for c in content.winning_patterns[:5]])
    lines.extend([f"- {c.claim}" for c in audience.purchase_motivations[:5]])
    lines.extend(["", "## 健康诊断"])
    lines.extend([f"- {x}" for x in diagnosis.main_strengths[:4]])
    lines.extend([f"- {x}" for x in diagnosis.main_weaknesses[:4]])
    lines.extend(["", "## 90 天改进目标"])
    lines.extend([f"- {x}" for x in diagnosis.next_90_days_targets[:5]])
    return "\n".join(lines).strip() + "\n"
