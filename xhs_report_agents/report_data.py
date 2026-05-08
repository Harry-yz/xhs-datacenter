from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import (
    AudienceInsights,
    ContentInsights,
    Diagnosis,
    EvidencePack,
    ExecutiveEditorial,
    ExternalContext,
    FactCheckResult,
    MetricAnalysis,
    ReportSection,
)
from .quality import ReportQualityGate


class ReportDataComposer:
    def compose(
        self,
        *,
        evidence: EvidencePack,
        metric: MetricAnalysis,
        content: ContentInsights,
        audience: AudienceInsights,
        diagnosis: Diagnosis,
        fact_check: FactCheckResult,
        executive: ExecutiveEditorial | None = None,
        external_context: ExternalContext | None = None,
        report_sections: list[ReportSection] | None = None,
    ) -> dict[str, Any]:
        editorial = executive or _fallback_editorial(evidence, metric, diagnosis)
        metrics = evidence.core_metrics
        topics = [item for item in evidence.keyword_signals if item.get("type") == "topic"]
        keywords = [item for item in evidence.keyword_signals if item.get("type") == "keyword"]
        coverage = [item for item in evidence.keyword_signals if str(item.get("type", "")).startswith("coverage_")]
        content_clusters = content.content_clusters or _topic_clusters(topics, metrics.note_count)
        competitor_benchmark = [{"brand": item.brand, **item.metrics.model_dump()} for item in evidence.competitor_metrics]
        competitor_positioning = _competitor_positioning(metrics, competitor_benchmark)
        keyword_matrix = _keyword_opportunity_matrix(
            keywords,
            content.search_keyword_opportunities,
            brand=evidence.brand,
            category=evidence.category,
            core_products=evidence.core_products,
        )
        confidence_summary = _confidence_summary(metric, content, audience, diagnosis, fact_check)
        evidence_groups = _evidence_group_summary(evidence)
        sections = report_sections or _fallback_sections(
            evidence=evidence,
            metric=metric,
            content=content,
            audience=audience,
            diagnosis=diagnosis,
            editorial=editorial,
            topics=topics,
        )
        report = {
            "report_meta": {
                "brand": evidence.brand,
                "report_type": "sales_15_xhs_brand_health",
                "primary_audience": "品牌市场负责人",
                "platform": "小红书",
            },
            "input_profile": {
                "brand": evidence.brand,
                "category": evidence.category,
                "core_products": evidence.core_products,
                "competitor_brands": evidence.competitors,
                "time_window_days": evidence.window_days,
                "expanded_terms": evidence.aliases,
            },
            "meta": {
                "brand": evidence.brand,
                "category": evidence.category,
                "core_products": evidence.core_products,
                "aliases": evidence.aliases,
                "competitors": evidence.competitors,
                "window_days": evidence.window_days,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "data_scope": "full_database_aggregation",
                "evidence_sample_note_count": len(evidence.top_notes),
                "evidence_sample_comment_count": len(evidence.comment_signals),
            },
            "data_scope": {
                "core_metrics": "full_database_aggregation",
                "evidence_sample_notes": len(evidence.top_notes),
                "evidence_sample_comments": len(evidence.comment_signals),
                "competitors": evidence.competitors,
                "coverage_diagnostics": coverage,
                "expanded_terms": evidence.aliases,
            },
            "editorial": editorial.model_dump(),
            "external_context": external_context.model_dump() if external_context else {},
            "kpis": {
                "health_score": round(metric.overall_score, 1),
                "note_count": metrics.note_count,
                "author_count": metrics.author_count,
                "interaction_total": metrics.interaction_total,
                "like_total": metrics.like_total,
                "comment_total": metrics.comment_total,
                "collection_total": metrics.collection_total,
                "share_total": metrics.share_total,
                "avg_interaction": metrics.avg_interaction,
                "avg_collection": metrics.avg_collection,
                "data_quality": evidence.data_quality.model_dump(),
            },
            "dimension_scores": [item.model_dump() for item in metric.dimension_scores],
            "health_score": round(metric.overall_score, 1),
            "kpi_cards": [
                {"label": "健康度", "value": round(metric.overall_score, 1), "hint": "/100"},
                {"label": "相关笔记", "value": metrics.note_count, "hint": "全量聚合"},
                {"label": "参与作者", "value": metrics.author_count, "hint": "去重作者"},
                {"label": "总互动", "value": metrics.interaction_total, "hint": "赞评藏转"},
            ],
            "benchmark_gap": metric.benchmark_gap,
            "metric_findings": [item.model_dump() for item in metric.metric_findings],
            "competitors": [
                {
                    "brand": item.brand,
                    **item.metrics.model_dump(),
                }
                for item in evidence.competitor_metrics
            ],
            "competitor_benchmark": competitor_benchmark,
            "competitor_positioning": competitor_positioning,
            "keywords": keywords[:32],
            "keyword_opportunity_matrix": keyword_matrix,
            "topics": topics[:24],
            "weekly_trend": [item for item in evidence.keyword_signals if item.get("type") == "weekly_trend"],
            "top_notes": [item.model_dump() for item in evidence.top_notes[:36]],
            "evidence_sample_groups": evidence_groups,
            "top_authors": [item.model_dump() for item in evidence.top_authors[:15]],
            "content": {
                "clusters": content_clusters,
                "winning_patterns": [item.model_dump() for item in content.winning_patterns],
                "underused_topics": content.underused_topics,
                "search_keyword_opportunities": content.search_keyword_opportunities,
                "content_formulas": content.content_formulas,
            },
            "content_clusters": content_clusters,
            "search_opportunities": content.search_keyword_opportunities,
            "audience": {
                "segments": audience.audience_segments,
                "purchase_motivations": [item.model_dump() for item in audience.purchase_motivations],
                "pain_points": [item.model_dump() for item in audience.pain_points],
                "usage_scenarios": audience.usage_scenarios,
                "confidence": audience.confidence,
                "limitations": audience.limitations,
            },
            "audience_segments": audience.audience_segments,
            "diagnosis": {
                "executive_findings": [item.model_dump() for item in diagnosis.executive_findings],
                "health_diagnosis": diagnosis.health_diagnosis,
                "main_strengths": diagnosis.main_strengths,
                "main_weaknesses": diagnosis.main_weaknesses,
                "next_90_days_targets": diagnosis.next_90_days_targets,
                "priority_actions": diagnosis.priority_actions,
            },
            "risk_opportunities": {
                "risks": metric.risks + diagnosis.main_weaknesses,
                "opportunities": content.underused_topics + content.search_keyword_opportunities,
            },
            "confidence_summary": confidence_summary,
            "chart_data": {
                "weekly_trend": [item for item in evidence.keyword_signals if item.get("type") == "weekly_trend"],
                "competitor_quadrant": competitor_positioning,
                "keyword_matrix": keyword_matrix,
                "confidence_summary": confidence_summary,
                "content_clusters": content_clusters,
            },
            "action_plan_90d": diagnosis.next_90_days_targets or diagnosis.priority_actions,
            "fact_check": fact_check.model_dump(),
            "report_sections": [item.model_dump() for item in sections],
        }
        report["quality_warnings"] = ReportQualityGate().evaluate(report)
        return report


def _fallback_editorial(evidence: EvidencePack, metric: MetricAnalysis, diagnosis: Diagnosis) -> ExecutiveEditorial:
    findings = [item.claim for item in diagnosis.executive_findings[:4]]
    if not findings:
        findings = [item.rationale for item in metric.dimension_scores[:4] if item.rationale]
    summary = f"{evidence.brand} 近 {evidence.window_days} 天小红书健康度为 {metric.overall_score:.1f}。"
    if evidence.data_quality.reasons:
        summary += " 当前结论已按数据质量限制降级表达。"
    return ExecutiveEditorial(
        title=f"{evidence.brand} 小红书品牌健康报告",
        subtitle=f"{evidence.category or '品牌'} · 近 {evidence.window_days} 天",
        executive_summary=summary,
        key_findings=findings[:5],
        management_diagnosis=str(diagnosis.health_diagnosis.get("summary") or summary),
        closing_note="报告指标来自确定性 SQL 聚合，洞察文本已经过事实校验。",
    )


def _topic_clusters(topics: list[dict[str, Any]], note_count: int) -> list[dict[str, Any]]:
    clusters = []
    denominator = max(note_count, 1)
    for item in topics[:12]:
        count = int(item.get("note_count") or 0)
        clusters.append(
            {
                "name": item.get("name") or item.get("topic") or "内容主题",
                "note_count": count,
                "interaction_total": int(item.get("interaction_total") or 0),
                "share": round(count / denominator * 100, 2),
                "basis": "database_tags",
            }
        )
    return clusters


def _competitor_positioning(brand_metrics, competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_notes = max(int(brand_metrics.note_count or 0), 1)
    baseline_efficiency = max(float(brand_metrics.avg_interaction or 0), 1.0)
    rows = [
        {
            "brand": "本品牌",
            "note_count": int(brand_metrics.note_count or 0),
            "avg_interaction": float(brand_metrics.avg_interaction or 0),
            "volume_index": 100.0,
            "efficiency_index": 100.0,
            "position": "基准",
            "caution": "",
        }
    ]
    for item in competitors:
        note_count = int(item.get("note_count") or 0)
        avg_interaction = float(item.get("avg_interaction") or 0)
        volume_index = round(note_count / baseline_notes * 100, 1)
        efficiency_index = round(avg_interaction / baseline_efficiency * 100, 1)
        if volume_index >= 80 and efficiency_index >= 110:
            position = "高声量高效率"
        elif volume_index >= 80:
            position = "高声量待提效"
        elif efficiency_index >= 130:
            position = "小样本高效率"
        else:
            position = "低声量低效率"
        rows.append(
            {
                "brand": item.get("brand") or "竞品",
                "note_count": note_count,
                "avg_interaction": avg_interaction,
                "volume_index": volume_index,
                "efficiency_index": efficiency_index,
                "position": position,
                "caution": "样本量明显低于本品牌，篇均互动不宜直接外推" if note_count < baseline_notes * 0.25 else "",
            }
        )
    return rows


class KeywordOpportunityScorer:
    def __init__(self, *, brand: str = "", category: str = "", core_products: list[str] | None = None, opportunities: list[str] | None = None):
        self.brand = brand.strip()
        self.category = category.strip()
        self.core_products = [item.strip() for item in (core_products or []) if item.strip()]
        self.opportunities = [item.strip() for item in (opportunities or []) if item.strip()]
        self.context = " ".join([self.brand, self.category, *self.core_products, *self.opportunities]).lower()
        self.domain_terms = _domain_terms(self.context)

    def score(self, keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for item in keywords[:48]:
            row = self._candidate(item)
            if row:
                candidates.append(row)
        if not candidates:
            return []
        demand_values = [item["_demand_raw"] for item in candidates]
        supply_values = [item["_supply_raw"] for item in candidates]
        for item in candidates:
            demand = _percentile(item["_demand_raw"], demand_values)
            supply_gap = _percentile(item["_supply_raw"], supply_values)
            intent = item.pop("_intent_score")
            relevance = item["relevance_score"]
            score = round(relevance * 0.40 + demand * 0.30 + supply_gap * 0.20 + intent * 0.10, 1)
            item["demand_score"] = round(demand, 1)
            item["supply_gap_score"] = round(supply_gap, 1)
            item["opportunity_score"] = min(96.0, max(12.0, score))
            item.pop("_demand_raw", None)
            item.pop("_supply_raw", None)
        return sorted(candidates, key=lambda x: (x["opportunity_score"], x["relevance_score"], x["interaction_total"]), reverse=True)

    def _candidate(self, item: dict[str, Any]) -> dict[str, Any] | None:
        keyword = str(item.get("search_keyword") or item.get("keyword") or "未标注")
        keyword = keyword.strip()
        if not keyword or keyword == "未标注":
            return None
        note_count = int(item.get("note_count") or 0)
        interaction_total = int(item.get("interaction_total") or 0)
        avg_interaction = round(interaction_total / note_count, 2) if note_count else 0
        relevance, category, reason = self._relevance(keyword)
        if relevance < 48:
            return None
        return {
            "keyword": keyword,
            "category": category,
            "note_count": note_count,
            "interaction_total": interaction_total,
            "avg_interaction": avg_interaction,
            "relevance_score": relevance,
            "reason": reason,
            "recommended_action": _keyword_action(keyword, category),
            "_demand_raw": _log_score(interaction_total) * 0.65 + _log_score(avg_interaction) * 0.35,
            "_supply_raw": 1 / max(note_count, 1),
            "_intent_score": _conversion_intent(keyword, category),
        }

    def _relevance(self, keyword: str) -> tuple[float, str, str]:
        key = keyword.lower()
        if self.brand and (self.brand.lower() in key or key in self.brand.lower()):
            return 96, "品牌词", "品牌主动搜索词，适合观察心智承接。"
        for product in self.core_products:
            p = product.lower()
            if p and (p in key or key in p):
                return 90, "产品词", "命中核心产品/产品线，适合转成内容选题。"
        if any(term in key for term in self.domain_terms["product"]):
            return 84, "产品/品类词", "命中品类或产品功效，和品牌经营目标相关。"
        if any(term in key for term in self.domain_terms["effect"]):
            return 80, "功效词", "命中用户问题或功效诉求，适合做转化型内容。"
        if any(term in key for term in self.domain_terms["scenario"]):
            return 68, "场景词", "命中使用场景，可用于拓展内容入口。"
        if any(key in item.lower() or item.lower() in key for item in self.opportunities if len(item) >= 2):
            return 62, "机会词", "被内容 Agent 标记为潜在机会，需结合样本复核。"
        if key in {"电脑", "软装", "运动", "彩妆", "面霜", "未标注"}:
            return 0, "弱相关词", "与当前品牌/品类弱相关，不进入机会矩阵。"
        if len(key) >= 2 and key in self.context:
            return 56, "上下文相关词", "出现在输入上下文中，但需要人工复核具体内容。"
        return 0, "泛搜索词", "缺少品牌、品类或功效相关性。"


def _keyword_opportunity_matrix(
    keywords: list[dict[str, Any]],
    opportunities: list[str],
    *,
    brand: str = "",
    category: str = "",
    core_products: list[str] | None = None,
) -> list[dict[str, Any]]:
    return KeywordOpportunityScorer(
        brand=brand,
        category=category,
        core_products=core_products or [],
        opportunities=opportunities,
    ).score(keywords)


def _domain_terms(context: str) -> dict[str, set[str]]:
    product = {"洗发", "洗发水", "洗发露", "护发", "头皮", "去屑", "头屑", "控油", "止痒", "蓬松", "发质", "发量", "脱发", "油头", "头油", "二硫化硒", "水杨酸"}
    effect = {"去屑", "控油", "止痒", "蓬松", "修护", "防脱", "脱发", "头皮痒", "敏感头皮", "油屑", "发缝"}
    scenario = {"熬夜", "夏天", "通勤", "学生党", "出油", "运动后", "姨妈期", "产后", "青春期"}
    if any(token in context for token in ("美妆", "护肤", "兰蔻", "精华", "面霜", "粉底", "防晒")):
        product |= {"精华", "面霜", "粉底", "眼霜", "防晒", "口红", "洁面", "爽肤水"}
        effect |= {"抗老", "修护", "美白", "保湿", "防晒", "敏感肌", "紧致", "暗沉"}
        scenario |= {"通勤", "约会", "旅行", "春日", "户外", "日常", "熬夜恢复"}
    return {"product": product, "effect": effect, "scenario": scenario}


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return 72.0
    below = sum(1 for item in sorted_values if item < value)
    equal = sum(1 for item in sorted_values if item == value)
    return round((below + equal * 0.5) / len(sorted_values) * 100, 1)


def _log_score(value: float) -> float:
    import math

    return math.log1p(max(value, 0))


def _conversion_intent(keyword: str, category: str) -> float:
    if category in {"产品词", "产品/品类词", "功效词"}:
        base = 78
    elif category == "品牌词":
        base = 64
    else:
        base = 48
    if any(token in keyword for token in ("去屑", "控油", "止痒", "防脱", "修护", "抗老", "美白", "防晒")):
        base += 12
    return min(100, base)


def _keyword_action(keyword: str, category: str) -> str:
    if category == "品牌词":
        return f"复盘“{keyword}”下高互动内容，稳定承接主动搜索需求。"
    if category in {"产品词", "产品/品类词"}:
        return f"围绕“{keyword}”产出测评、使用教程和横向对比内容。"
    if category == "功效词":
        return f"用真实问题场景解释“{keyword}”相关功效，补充评论区答疑。"
    return f"小规模测试“{keyword}”场景内容，验证是否能带来新增互动。"


def _confidence_summary(metric, content, audience, diagnosis, fact_check) -> dict[str, Any]:
    claims = []
    for item in metric.dimension_scores:
        claims.append({"source": "health_dimension", "label": item.name, "confidence": item.confidence})
    for source, items in (
        ("metric", metric.metric_findings),
        ("content", content.winning_patterns),
        ("audience_motivation", audience.purchase_motivations),
        ("audience_pain", audience.pain_points),
        ("diagnosis", diagnosis.executive_findings),
        ("fact_approved", fact_check.approved_claims),
        ("fact_downgraded", fact_check.downgraded_claims),
    ):
        for item in items:
            claims.append({"source": source, "label": item.claim, "confidence": item.confidence})
    counts = {"high": 0, "medium": 0, "low": 0}
    for item in claims:
        if item["confidence"] in counts:
            counts[item["confidence"]] += 1
    total = max(len(claims), 1)
    return {
        "counts": counts,
        "strong_evidence_ratio": round(counts["high"] / total * 100, 1),
        "claim_count": len(claims),
        "sample": claims[:24],
    }


def _evidence_group_summary(evidence: EvidencePack) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for note in evidence.top_notes:
        group = note.sample_group or "unknown"
        item = grouped.setdefault(group, {"sample_group": group, "note_count": 0, "interaction_total": 0, "collection_total": 0, "comment_total": 0})
        item["note_count"] += 1
        item["interaction_total"] += note.interaction_total
        item["collection_total"] += note.collection_count
        item["comment_total"] += note.comment_count
    return list(grouped.values())


SECTION_TITLES = [
    "封面与报告范围",
    "管理层摘要",
    "核心指标速览",
    "关键发现",
    "小红书平台与品类机会",
    "品牌小红书现状盘点",
    "六维品牌健康评分体系",
    "内容声量与趋势",
    "互动质量与内容资产",
    "竞品对标与差距诊断",
    "内容主题与爆文拆解",
    "搜索占位与关键词机会",
    "用户洞察：人群、动机、痛点、场景",
    "品牌风险与增长机会",
    "90 天方向与动作清单",
]


def _fallback_sections(
    *,
    evidence: EvidencePack,
    metric: MetricAnalysis,
    content: ContentInsights,
    audience: AudienceInsights,
    diagnosis: Diagnosis,
    editorial: ExecutiveEditorial,
    topics: list[dict[str, Any]],
) -> list[ReportSection]:
    metrics = evidence.core_metrics
    competitors = evidence.competitor_metrics
    keywords = [item for item in evidence.keyword_signals if item.get("type") == "keyword"][:8]
    top_notes = evidence.top_notes[:8]
    sections: list[ReportSection] = []
    common_evidence = [
        f"近 {evidence.window_days} 天全量相关笔记 {metrics.note_count} 条",
        f"参与作者 {metrics.author_count} 个，总互动 {metrics.interaction_total}",
    ]
    for idx, title in enumerate(SECTION_TITLES, start=1):
        section_id = f"section-{idx:02d}"
        if idx == 1:
            body = [editorial.executive_summary or f"本报告评估 {evidence.brand} 在小红书的品牌健康度、内容资产、搜索占位、用户反馈和竞品位置。"]
            bullets = [f"报告对象：{evidence.brand}", f"品类：{evidence.category or '未标注'}", f"核心产品：{'、'.join(evidence.core_products) or '未标注'}", f"分析窗口：近 {evidence.window_days} 天"]
            table = [{"指标": "核心产品", "当前值": "、".join(evidence.core_products) or "未标注"}, {"指标": "竞品品牌", "当前值": "、".join(evidence.competitors)}]
        elif idx == 2:
            body = [editorial.management_diagnosis or editorial.executive_summary or "品牌具备可分析的内容资产和搜索声量，需要结合互动效率、竞品差距和用户反馈判断下一步增长机会。"]
            bullets = editorial.key_findings[:5] or [item.claim for item in diagnosis.executive_findings[:5]]
            table = []
        elif idx == 3:
            body = ["核心指标用于快速判断品牌在小红书的可见度、内容效率和用户反馈厚度。售前沟通中应重点解释声量是否形成资产、互动是否有效、搜索词是否被品牌承接。"]
            bullets = [f"健康度 {metric.overall_score:.1f}/100", f"篇均互动 {metrics.avg_interaction}", f"收藏总量 {metrics.collection_total}", f"评论总量 {metrics.comment_total}"]
            table = [{"指标": "笔记数", "当前值": metrics.note_count}, {"指标": "作者数", "当前值": metrics.author_count}, {"指标": "总互动", "当前值": metrics.interaction_total}]
        elif idx == 4:
            claims = diagnosis.executive_findings or metric.metric_findings
            body = ["关键发现用于建立售前讨论的主线：先说明品牌当前位置，再指出增长瓶颈，最后引出我们可以帮助品牌优化的方向。"]
            bullets = [item.claim for item in claims[:5]] or editorial.key_findings[:5]
            table = []
        elif idx == 5:
            body = [f"小红书对 {evidence.category or evidence.brand} 的价值在于同时承接搜索、种草、内容资产和用户反馈。报告不把平台当作单纯曝光渠道，而是评估品牌是否围绕核心产品形成可持续的内容经营能力。"]
            bullets = ["搜索词承接决定用户主动需求能否被捕捉", "收藏和评论反映内容是否具备决策价值", f"核心产品优先看：{'、'.join(evidence.core_products) or evidence.brand}"]
            table = [{"机会": item.get("search_keyword", ""), "笔记数": item.get("note_count", 0), "互动": item.get("interaction_total", 0)} for item in keywords[:5]]
        elif idx == 6:
            body = [f"{evidence.brand} 当前在数据库中具备 {metrics.note_count} 条相关笔记和 {metrics.author_count} 个参与作者。下一步需要判断这些声量是否真正围绕 {'、'.join(evidence.core_products) or '核心产品'} 沉淀为内容资产。"]
            bullets = [f"总互动 {metrics.interaction_total}", f"收藏 {metrics.collection_total}", f"分享 {metrics.share_total}"]
            table = [{"标题": note.title, "作者": note.author_nickname, "互动": note.interaction_total} for note in top_notes[:5]]
        elif idx == 7:
            body = ["六维评分用于把复杂内容生态压缩成管理层可读的诊断框架。分数不是销售预测，而是品牌在小红书经营成熟度的横向观察。"]
            bullets = [f"{item.name}: {item.score:.1f} - {item.rationale}" for item in metric.dimension_scores[:6]]
            table = [{"维度": item.name, "得分": item.score, "置信度": item.confidence} for item in metric.dimension_scores[:6]]
        elif idx == 8:
            body = ["内容声量需要和趋势一起看。短期声量高说明品牌容易被召回，但如果趋势由少数爆文或单一主题驱动，后续增长稳定性仍需要谨慎判断。"]
            bullets = [f"相关笔记 {metrics.note_count}", f"作者覆盖 {metrics.author_count}", "建议按周追踪声量和互动变化"]
            table = [item for item in evidence.keyword_signals if item.get("type") == "weekly_trend"][-8:]
        elif idx == 9:
            body = ["互动质量决定内容能否从曝光转化为真实兴趣。收藏代表回看和决策价值，评论代表疑问和讨论，分享代表二次传播。"]
            bullets = [f"篇均互动 {metrics.avg_interaction}", f"篇均收藏 {metrics.avg_collection}", f"评论总量 {metrics.comment_total}"]
            table = [{"内容": note.title, "互动": note.interaction_total, "收藏": note.collection_count, "评论": note.comment_count} for note in top_notes[:6]]
        elif idx == 10:
            body = ["竞品对标用于判断问题是品牌自身短板，还是品类共同现象。售前沟通应优先抓住与主要竞品差距最大的指标。"]
            bullets = metric.benchmark_gap[:5] or [f"竞品数量：{len(competitors)}"]
            table = [{"品牌": item.brand, "笔记": item.metrics.note_count, "作者": item.metrics.author_count, "篇均互动": item.metrics.avg_interaction} for item in competitors]
        elif idx == 11:
            body = ["内容主题和爆文拆解用于回答：品牌靠什么内容被看见，哪些主题可以复用，哪些主题只是偶发。"]
            bullets = [item.claim for item in content.winning_patterns[:5]] or [str(item.get("name")) for item in topics[:5]]
            table = [{"主题": item.get("name", ""), "笔记数": item.get("note_count", 0), "互动": item.get("interaction_total", 0)} for item in topics[:8]]
        elif idx == 12:
            body = ["搜索占位反映用户主动需求是否被品牌接住。品牌词强只能说明已有认知，产品词和场景词才更接近新增需求。"]
            bullets = content.search_keyword_opportunities[:6] or [item.get("search_keyword", "") for item in keywords[:6]]
            table = [{"关键词": item.get("search_keyword", ""), "笔记数": item.get("note_count", 0), "互动": item.get("interaction_total", 0)} for item in keywords[:8]]
        elif idx == 13:
            body = ["用户洞察主要来自评论、笔记文本、搜索词和内容场景。报告不强行推断年龄收入，而是聚焦用户动机、痛点和使用场景。"]
            bullets = [item.claim for item in audience.purchase_motivations[:4]] + [item.claim for item in audience.pain_points[:4]]
            table = audience.audience_segments[:6]
        elif idx == 14:
            body = ["风险与机会用于把健康诊断转化为售前切入点。风险不是为了制造焦虑，而是帮助客户看见当前小红书经营中最应该优先处理的结构问题。"]
            bullets = diagnosis.main_weaknesses[:4] + content.underused_topics[:3]
            table = [{"类型": "风险", "内容": item} for item in diagnosis.main_weaknesses[:4]] + [{"类型": "机会", "内容": item} for item in content.underused_topics[:4]]
        else:
            body = ["90 天动作清单用于把诊断转成可执行方向。售前阶段不展开完整 SOP，但需要明确优先级、抓手和预期改善方向。"]
            bullets = diagnosis.priority_actions[:6] or diagnosis.next_90_days_targets[:6]
            table = [{"优先级": f"P{i}", "动作": item} for i, item in enumerate((diagnosis.next_90_days_targets or diagnosis.priority_actions)[:6], start=0)]
        sections.append(
            ReportSection(
                section_id=section_id,
                title=title,
                eyebrow="小红书品牌健康度售前诊断",
                core_judgment=(body[0][:120] if body else f"{title}需要结合全量数据判断。"),
                evidence=common_evidence,
                body=body,
                bullets=[item for item in bullets if item][:6],
                table=table[:10] if isinstance(table, list) else [],
                cards=[],
            )
        )
    return sections
