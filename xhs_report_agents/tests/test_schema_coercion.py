from __future__ import annotations

from xhs_report_agents.schemas import AudienceInsights, ContentInsights, Diagnosis, ExecutiveEditorial, FactCheckResult, MetricAnalysis


def test_metric_analysis_coerces_deepseek_shape_variants():
    parsed = MetricAnalysis.model_validate(
        {
            "overall_score": 82,
            "dimension_scores": [
                {
                    "name": "声量渗透",
                    "score": 90,
                    "confidence": 0.7,
                    "rationale": "样本充足",
                    "evidence_ids": ["N1"],
                }
            ],
            "benchmark_gap": {"description": "与YSL相比声量更高"},
            "metric_findings": [
                {"claim": "兰蔻声量基础较强", "evidence_ids": ["N1"], "confidence": 0.8}
            ],
            "risks": [{"description": "互动数据仍需持续补齐"}],
        }
    )
    assert parsed.dimension_scores[0].confidence == "medium"
    assert parsed.metric_findings[0].confidence == "high"
    assert parsed.benchmark_gap == ["与YSL相比声量更高"]
    assert parsed.risks == ["互动数据仍需持续补齐"]


def test_audience_insights_coerces_string_segments_and_limitations():
    parsed = AudienceInsights.model_validate(
        {
            "audience_segments": ["抗老护肤需求者", "彩妆爱好者"],
            "purchase_motivations": ["关注修护和功效"],
            "pain_points": "担心敏感肌适配",
            "usage_scenarios": "通勤妆",
            "confidence": 0.4,
            "limitations": "未获取用户年龄、城市等结构化数据。",
        }
    )
    assert parsed.audience_segments[0]["name"] == "抗老护肤需求者"
    assert parsed.purchase_motivations[0].claim == "关注修护和功效"
    assert parsed.pain_points[0].claim == "担心敏感肌适配"
    assert parsed.usage_scenarios == ["通勤妆"]
    assert parsed.confidence == "low"
    assert parsed.limitations == ["未获取用户年龄、城市等结构化数据。"]


def test_other_agent_outputs_coerce_common_variants():
    content = ContentInsights.model_validate(
        {
            "content_clusters": ["防晒测评"],
            "winning_patterns": "清单式标题表现更稳定",
            "underused_topics": {"description": "敏感肌适配"},
            "search_keyword_opportunities": "兰蔻小白管",
            "content_formulas": "品牌词 + 场景",
        }
    )
    diagnosis = Diagnosis.model_validate(
        {
            "executive_findings": "品牌声量基础强",
            "health_diagnosis": "品牌健康度处于强势区间",
            "main_strengths": "声量强",
            "main_weaknesses": {"description": "评论洞察不足"},
            "next_90_days_targets": "提升收藏型内容占比",
            "priority_actions": "补齐评论采集",
        }
    )
    fact = FactCheckResult.model_validate(
        {
            "approved_claims": "品牌声量基础强",
            "downgraded_claims": {"description": "达人结构判断证据偏弱"},
            "removed_claims": {"description": "无证据销售增长判断"},
            "required_disclaimers": "仅基于当前数据库样本",
        }
    )
    assert content.content_clusters[0]["name"] == "防晒测评"
    assert diagnosis.health_diagnosis == {"summary": "品牌健康度处于强势区间"}
    assert diagnosis.main_weaknesses == ["评论洞察不足"]
    assert fact.required_disclaimers == ["仅基于当前数据库样本"]


def test_executive_editorial_coerces_key_findings():
    parsed = ExecutiveEditorial.model_validate(
        {
            "title": "兰蔻报告",
            "subtitle": "全量聚合",
            "executive_summary": "摘要",
            "key_findings": {"description": "声量基础较强"},
            "management_diagnosis": "诊断",
        }
    )
    assert parsed.key_findings == ["声量基础较强"]
