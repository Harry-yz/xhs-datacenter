from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from ..llm_client import DeepSeekClient
from ..schemas import (
    AudienceInsights,
    Claim,
    ContentInsights,
    Diagnosis,
    DimensionScore,
    ExecutiveEditorial,
    ExternalContext,
    FactCheckResult,
    MetricAnalysis,
    SectionWriterOutput,
)
from ..report_data import _fallback_sections

ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonAgent:
    def __init__(self, *, name: str, prompt: str, client: DeepSeekClient, model: str | None = None):
        self.name = name
        self.prompt = prompt
        self.client = client
        self.model = model

    def run(self, payload: dict[str, Any], schema: type[ModelT]) -> ModelT:
        response = self.client.complete_json(
            system=self.prompt,
            user=json.dumps(payload, ensure_ascii=False, default=str),
            model=self.model,
        )
        return schema.model_validate(response)


class OfflineAgent:
    def __init__(self, *, name: str):
        self.name = name

    def run(self, payload: dict[str, Any], schema: type[ModelT]) -> ModelT:
        evidence = payload.get("evidence_pack", {})
        metrics = evidence.get("core_metrics", {})
        quality = evidence.get("data_quality", {})
        notes = evidence.get("top_notes", [])
        note_count = int(metrics.get("note_count") or 0)
        author_count = int(metrics.get("author_count") or 0)
        interaction_total = int(metrics.get("interaction_total") or 0)
        confidence = "low" if quality.get("status") in {"limited", "warning"} else "medium"

        if schema is MetricAnalysis:
            score = _bounded_score(note_count, author_count, interaction_total, quality.get("reasons", []))
            data = MetricAnalysis(
                overall_score=score,
                dimension_scores=[
                    DimensionScore(name="声量渗透", score=min(100, note_count * 2), confidence=confidence, rationale="基于样本笔记数量和时间窗内品牌文本命中。", evidence_ids=["N1"] if notes else []),
                    DimensionScore(name="互动质量", score=score if interaction_total else 35, confidence=confidence, rationale="基于点赞、评论、收藏、分享和总互动字段；字段稀疏时降低置信度。", evidence_ids=["N1"] if notes else []),
                    DimensionScore(name="内容资产", score=min(100, max(20, len(notes) * 3)), confidence=confidence, rationale="基于可见高相关笔记和主题覆盖。", evidence_ids=[n.get("evidence_id", "") for n in notes[:3]]),
                    DimensionScore(name="搜索占位", score=min(100, max(20, note_count * 1.5)), confidence=confidence, rationale="基于搜索关键词和文本命中样本。", evidence_ids=[]),
                    DimensionScore(name="达人结构", score=min(100, max(20, author_count * 3)), confidence=confidence, rationale="基于参与作者数量和头部作者集中度。", evidence_ids=[]),
                    DimensionScore(name="转化潜力", score=45 if interaction_total == 0 else min(100, 45 + int(metrics.get("collection_total") or 0)), confidence=confidence, rationale="基于收藏、评论与内容场景信号。", evidence_ids=[]),
                ],
                metric_findings=[
                    {"claim": f"近 {evidence.get('window_days')} 天样本中共识别 {note_count} 条品牌相关笔记。", "evidence_ids": ["N1"] if notes else [], "confidence": confidence}
                ],
                risks=list(quality.get("notes") or []),
            )
            return schema.model_validate(data.model_dump())
        if schema is ContentInsights:
            data = ContentInsights(
                winning_patterns=[
                    {"claim": "当前可见内容应优先围绕高频标题词、场景词和收藏导向主题继续拆解。", "evidence_ids": [n.get("evidence_id", "") for n in notes[:3]], "confidence": confidence}
                ],
                search_keyword_opportunities=[x.get("search_keyword", "") for x in evidence.get("keyword_signals", [])[:8] if x.get("search_keyword")],
                content_formulas=["品牌词 + 使用场景 + 具体问题/清单式标题", "产品/品牌出现 + 真实体验描述 + 评论区承接"],
            )
            return schema.model_validate(data.model_dump())
        if schema is AudienceInsights:
            data = AudienceInsights(
                audience_segments=[{"name": "品牌搜索与兴趣用户", "basis": "来自品牌词命中笔记、搜索关键词和评论样本。"}],
                purchase_motivations=[{"claim": "受众洞察需要结合更多评论和互动补齐后提升置信度。", "evidence_ids": [], "confidence": "low"}],
                confidence="low" if "comments_insufficient" in quality.get("reasons", []) else confidence,
                limitations=list(quality.get("notes") or []),
            )
            return schema.model_validate(data.model_dump())
        if schema is Diagnosis:
            data = Diagnosis(
                executive_findings=[
                    {"claim": "品牌健康度第一版诊断应以样本声量、内容覆盖和数据质量并列解读。", "evidence_ids": ["N1"] if notes else [], "confidence": confidence}
                ],
                health_diagnosis={"summary": "离线模式生成的本地诊断，用于验证链路和模板。"},
                main_strengths=["已有可召回的品牌相关笔记样本。"],
                main_weaknesses=list(quality.get("notes") or ["需要补充更完整的互动和评论数据。"]),
                next_90_days_targets=["提升可追踪样本量和互动字段完整度。", "沉淀品牌关键词与高表现内容主题。"],
                priority_actions=["补齐详情互动数据。", "按主题聚类复盘高相关内容。"],
            )
            return schema.model_validate(data.model_dump())
        if schema is FactCheckResult:
            data = FactCheckResult(
                approved_claims=[{"claim": "当前报告结论基于数据库可见样本和数据质量标记。", "evidence_ids": [], "confidence": confidence}],
                required_disclaimers=list(quality.get("notes") or []),
            )
            return schema.model_validate(data.model_dump())
        if schema is ExecutiveEditorial:
            brand = evidence.get("brand", "品牌")
            score = _bounded_score(note_count, author_count, interaction_total, quality.get("reasons", []))
            data = ExecutiveEditorial(
                title=f"{brand} 小红书品牌健康报告",
                subtitle=f"基于近 {evidence.get('window_days', 90)} 天数据库全量相关笔记聚合",
                executive_summary=f"{brand} 当前健康度为 {score:.1f}/100，报告基于全量相关笔记聚合和抽样证据生成。",
                key_findings=[
                    f"全量聚合识别 {note_count} 条相关笔记、{author_count} 个参与作者。",
                    "互动、评论或详情字段不足时，结论已按数据质量限制降级。",
                ],
                management_diagnosis="离线模式总编摘要，用于验证链路、数据结构和高级 HTML 模板。",
                closing_note="所有核心指标来自确定性 SQL 聚合。",
            )
            return schema.model_validate(data.model_dump())
        if schema is ExternalContext:
            brand = evidence.get("brand", "品牌")
            data = ExternalContext(
                category_context=["小红书美妆护肤内容通常围绕功效、场景、真实体验和搜索词承接展开。"],
                platform_context=["小红书品牌健康度应同时观察声量、互动、收藏、评论、搜索和作者结构。"],
                brand_context=[f"{brand} 的诊断应优先回到数据库中的笔记、关键词、评论和竞品对比。"],
                cautions=list(quality.get("notes") or []),
            )
            return schema.model_validate(data.model_dump())
        if schema is SectionWriterOutput:
            metric = MetricAnalysis.model_validate(payload.get("metric_analysis", {"overall_score": _bounded_score(note_count, author_count, interaction_total, quality.get("reasons", [])), "dimension_scores": []}))
            content = ContentInsights.model_validate(payload.get("content_insights", {}))
            audience = AudienceInsights.model_validate(payload.get("audience_insights", {}))
            diagnosis = Diagnosis.model_validate(payload.get("diagnosis", {}))
            editorial = ExecutiveEditorial.model_validate(payload.get("executive_editorial", {}))
            pack = payload.get("full_evidence_pack") or evidence
            evidence_pack = payload.get("_evidence_model")
            if evidence_pack is None:
                from ..schemas import EvidencePack

                evidence_pack = EvidencePack.model_validate(pack)
            topics = [item for item in evidence.get("keyword_signals", []) if item.get("type") == "topic"]
            sections = _fallback_sections(
                evidence=evidence_pack,
                metric=metric,
                content=content,
                audience=audience,
                diagnosis=diagnosis,
                editorial=editorial,
                topics=topics,
            )
            return schema.model_validate({"report_sections": [item.model_dump() for item in sections]})
        if "markdown" in getattr(schema, "model_fields", {}):
            brand = evidence.get("brand", "品牌")
            metric_analysis = payload.get("metric_analysis", {})
            content_insights = payload.get("content_insights", {})
            audience_insights = payload.get("audience_insights", {})
            diagnosis = payload.get("diagnosis", {})
            fact_check = payload.get("fact_check", {})
            markdown = _offline_report_markdown(
                brand=brand,
                evidence=evidence,
                metric_analysis=metric_analysis,
                content_insights=content_insights,
                audience_insights=audience_insights,
                diagnosis=diagnosis,
                fact_check=fact_check,
            )
            return schema.model_validate({"markdown": markdown})
        return schema.model_validate({})


def _offline_report_markdown(
    *,
    brand: str,
    evidence: dict[str, Any],
    metric_analysis: dict[str, Any],
    content_insights: dict[str, Any],
    audience_insights: dict[str, Any],
    diagnosis: dict[str, Any],
    fact_check: dict[str, Any],
) -> str:
    metrics = evidence.get("core_metrics", {})
    quality = evidence.get("data_quality", {})
    competitors = evidence.get("competitor_metrics", [])
    dimensions = metric_analysis.get("dimension_scores", [])
    top_notes = evidence.get("top_notes", [])
    top_authors = evidence.get("top_authors", [])
    keywords = evidence.get("keyword_signals", [])
    score = float(metric_analysis.get("overall_score") or 0)
    note_count = int(metrics.get("note_count") or 0)
    author_count = int(metrics.get("author_count") or 0)
    interaction_total = int(metrics.get("interaction_total") or 0)
    collection_total = int(metrics.get("collection_total") or 0)
    comment_total = int(metrics.get("comment_total") or 0)
    avg_interaction = float(metrics.get("avg_interaction") or 0)
    best_dimension = _best_dimension(dimensions)
    weak_dimension = _weak_dimension(dimensions)

    findings = [
        f"{brand} 在当前小红书样本中识别到 {note_count} 条相关笔记、{author_count} 个参与作者，说明已有稳定的内容声量基础。",
        f"健康度综合分为 {score:.1f}/100；强项集中在 {best_dimension}，优先补强项是 {weak_dimension}。",
        _quality_finding(quality),
    ]
    comp_rows = _competitor_rows(competitors)
    dim_rows = "\n".join(
        f"| {d.get('name','-')} | {float(d.get('score') or 0):.1f} | {d.get('confidence','medium')} | {d.get('rationale','')} |"
        for d in dimensions
    ) or "| 暂无 | 0 | low | 数据不足 |"
    top_note_rows = "\n".join(
        f"| {n.get('evidence_id','')} | { _safe(n.get('title','')) } | { _safe(n.get('author_nickname','')) } | {int(n.get('interaction_total') or 0)} | {int(n.get('collection_count') or 0)} |"
        for n in top_notes[:10]
    ) or "| - | 暂无 | - | 0 | 0 |"
    author_rows = "\n".join(
        f"| {a.get('author_nickname') or a.get('author_id') or '-'} | {int(a.get('note_count') or 0)} | {int(a.get('fans_count') or 0)} | {int(a.get('interaction_total') or 0)} |"
        for a in top_authors[:10]
    ) or "| - | 0 | 0 | 0 |"
    keyword_list = "、".join(str(k.get("search_keyword")) for k in keywords[:10] if k.get("search_keyword")) or "暂无稳定搜索关键词"
    data_notes = "\n".join(f"- {x}" for x in quality.get("notes", [])) or "- 当前样本未发现明显数据质量限制。"
    disclaimers = "\n".join(f"- {x}" for x in fact_check.get("required_disclaimers", []))
    if disclaimers:
        data_notes = f"{data_notes}\n{disclaimers}"

    return f"""# {brand} 小红书品牌健康度洞察报告

## 六维核心指标速览
| 指标 | 当前值 | 解读 |
| --- | ---: | --- |
| 品牌健康度总分 | {score:.1f}/100 | 综合声量、互动、内容资产、搜索占位、达人结构和转化潜力 |
| 相关笔记数 | {note_count} | 当前窗口内品牌相关内容样本 |
| 参与作者数 | {author_count} | 衡量达人/用户覆盖宽度 |
| 总互动 | {interaction_total} | 点赞、评论、收藏、分享等字段汇总 |
| 收藏总量 | {collection_total} | 高意向内容资产信号 |
| 评论总量 | {comment_total} | 讨论与反馈信号 |
| 篇均互动 | {avg_interaction:.2f} | 内容效率参考值 |

## 三个最关键发现
- {findings[0]}
- {findings[1]}
- {findings[2]}

## 第一部分 · 平台与品牌现状
本报告基于现有小红书数据库，对 {brand} 在近 {evidence.get('window_days', 90)} 天的可见内容进行品牌健康度诊断。当前分析优先采用已建索引的品牌词、搜索词和笔记事实表，避免大表全文扫描导致报告生成不稳定。

## 01 · 为什么看小红书：平台价值与品类机会
小红书对美妆品牌的价值主要体现在搜索承接、内容种草、达人扩散和评论反馈。对 {brand} 这类成熟品牌来说，健康度不只看声量，也要看内容是否形成可复用资产、搜索词是否稳定占位、达人结构是否足够分散。

## 02 · {brand} 品牌小红书现状盘点
当前样本中，{brand} 相关笔记数为 {note_count}，参与作者数为 {author_count}，总互动为 {interaction_total}。如果互动字段存在缺失，本报告不会把 0 互动直接解读为用户兴趣不足，而是把它作为数据质量限制处理。

## 第二部分 · 健康度评分
健康度总分为 **{score:.1f}/100**。该分数用于横向诊断和后续跟踪，不等同于销售结果。

## 03 · 健康度评分体系
评分体系包含六个维度：声量渗透、互动质量、内容资产、搜索占位、达人结构、转化潜力。每个维度都必须回到数据库样本，不使用外部案例或未经验证的市场判断。

## 3.1 内容声量变化
样本内 {brand} 相关笔记数为 {note_count}。声量越高，说明品牌在当前数据库可见范围内越容易被召回；但声量本身不代表内容质量，还需要结合收藏、评论和作者分布判断。

## 3.2 角色互动效率
总互动为 {interaction_total}，篇均互动为 {avg_interaction:.2f}。如果详情接口曾经未补齐，互动类指标需要作为趋势参考，而不是绝对结论。

## 3.3 内容生态结构
当前高相关笔记样例如下：

| 证据ID | 标题 | 作者 | 互动 | 收藏 |
| --- | --- | --- | ---: | ---: |
{top_note_rows}

## 3.4 互动质量评分
| 维度 | 得分 | 置信度 | 依据 |
| --- | ---: | --- | --- |
{dim_rows}

## 3.5 小红书站内搜索表现
当前可见搜索关键词包括：{keyword_list}。这些词可作为后续内容标题、合集页和达人 brief 的关键词池。

## 3.6 转化潜力与内容资产
收藏总量为 {collection_total}，评论总量为 {comment_total}。收藏更接近“回看/种草/待购买”信号，评论更接近“疑问/反馈/讨论”信号；两者都应优先用于筛选可复用内容主题。

## 第三部分 · 受众洞察
当前受众洞察主要来自笔记文本、搜索词、作者结构和评论样本。若评论样本不足，受众画像置信度需要降低。

## 04 · 目标受众洞察
{_claims_text(audience_insights.get('purchase_motivations', []), '当前样本显示，受众洞察仍需更多评论数据补齐。')}

## 第四部分 · 结论
{brand} 当前具备较好的品牌可见基础，但报告最应关注的不是单点爆文，而是“关键词占位、内容资产化、达人结构分散度、互动字段完整度”的持续改善。

## 05 · 品牌健康度诊断
- 主要优势：{'; '.join(diagnosis.get('main_strengths', []) or ['已有可召回的品牌相关笔记样本'])}
- 主要短板：{'; '.join(diagnosis.get('main_weaknesses', []) or ['需要补齐评论与互动数据，提高诊断置信度'])}
- 优先动作：{'; '.join(diagnosis.get('priority_actions', []) or ['补齐详情互动数据', '按主题聚类复盘高相关内容'])}

## 6 个月目标拆解
| 维度 | 当前值 | 6 个月目标 | 驱动动作 |
| --- | ---: | --- | --- |
| 品牌声量 | {note_count} 条 | 稳定提升样本覆盖 | 围绕核心搜索词持续发布内容 |
| 作者覆盖 | {author_count} 个 | 提高作者分散度 | 增加腰部/垂类达人协同 |
| 内容资产 | {collection_total} 收藏 | 提升高收藏内容占比 | 复用清单、测评、场景内容公式 |
| 评论反馈 | {comment_total} 评论 | 提高评论样本可分析度 | 优先补齐评论采集和问题归类 |

## 行动方向（概述级）
- 用搜索关键词池指导标题和内容 brief，优先抢占高频搜索场景。
- 将高收藏笔记拆解成可复用内容公式，而不是只看点赞。
- 按作者互动与内容主题建立达人池，避免只依赖少数头部账号。
- 补齐详情互动与评论数据，让下轮健康度评分更接近真实表现。

## CLOSING DIAGNOSIS
{brand} 的当前健康度诊断结论是：品牌有可见声量和内容基础，但要进一步从“有内容”走向“有资产”，关键在于搜索词占位、收藏型内容沉淀、达人结构优化和数据完整度提升。

## 数据说明
{data_notes}
"""


def _best_dimension(dimensions: list[dict[str, Any]]) -> str:
    if not dimensions:
        return "样本覆盖"
    item = max(dimensions, key=lambda x: float(x.get("score") or 0))
    return str(item.get("name") or "样本覆盖")


def _weak_dimension(dimensions: list[dict[str, Any]]) -> str:
    if not dimensions:
        return "数据完整度"
    item = min(dimensions, key=lambda x: float(x.get("score") or 0))
    return str(item.get("name") or "数据完整度")


def _quality_finding(quality: dict[str, Any]) -> str:
    reasons = quality.get("reasons", [])
    if "metrics_sparse" in reasons:
        return "互动字段存在稀疏风险，因此不能把低互动直接解释为品牌表现弱。"
    if "comments_insufficient" in reasons:
        return "评论样本不足，受众洞察需要以低置信度方式呈现。"
    return "当前样本的数据质量可以支持第一版品牌健康度诊断。"


def _competitor_rows(competitors: list[dict[str, Any]]) -> str:
    if not competitors:
        return ""
    return "\n".join(
        f"| {c.get('brand','-')} | {int((c.get('metrics') or {}).get('note_count') or 0)} | {int((c.get('metrics') or {}).get('interaction_total') or 0)} |"
        for c in competitors[:8]
    )


def _claims_text(claims: list[dict[str, Any]], fallback: str) -> str:
    if not claims:
        return fallback
    return "\n".join(f"- {c.get('claim', '')}" for c in claims if c.get("claim"))


def _safe(value: Any) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    return text[:80] + "…" if len(text) > 80 else text


def _bounded_score(note_count: int, author_count: int, interaction_total: int, reasons: list[str]) -> float:
    score = min(85, 25 + note_count * 1.2 + author_count * 0.8 + min(interaction_total, 1000) / 50)
    if "metrics_sparse" in reasons:
        score -= 12
    if "sample_size_low" in reasons:
        score -= 10
    return round(max(20, score), 1)
