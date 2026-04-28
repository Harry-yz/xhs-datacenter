from __future__ import annotations

from xhs_report_agents.renderers.html import HtmlRenderer
from xhs_report_agents.schemas import (
    AudienceInsights,
    ContentInsights,
    DataQuality,
    Diagnosis,
    EvidencePack,
    FactCheckResult,
    MetricAnalysis,
    MetricBlock,
    ReportBundle,
)


def test_html_renderer_embeds_report_data():
    evidence = EvidencePack(
        brand="测试品牌",
        aliases=["测试品牌"],
        competitors=[],
        window_days=90,
        generated_at="2026-04-28T00:00:00",
        core_metrics=MetricBlock(note_count=3, author_count=2, interaction_total=10),
        data_quality=DataQuality(status="ok"),
    )
    bundle = ReportBundle(
        evidence_pack=evidence,
        metric_analysis=MetricAnalysis(overall_score=66, dimension_scores=[]),
        content_insights=ContentInsights(),
        audience_insights=AudienceInsights(),
        diagnosis=Diagnosis(),
        fact_check=FactCheckResult(),
        markdown="# 测试品牌 小红书品牌健康报告\n\n## 核心指标速览\n- 样本笔记：3\n",
    )
    html = HtmlRenderer().render(bundle)
    assert "测试品牌 小红书品牌健康报告" in html
    assert 'id="report-data"' in html
    assert "相关笔记" in html
    assert "Markdown" not in html
