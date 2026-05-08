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


def test_html_renderer_uses_keyword_cards_and_long_text_cards():
    report = {
        "meta": {"brand": "测试品牌", "window_days": 90, "generated_at": "2026-05-08T00:00:00"},
        "editorial": {"title": "测试品牌 小红书品牌健康报告", "executive_summary": "摘要"},
        "kpis": {"health_score": 80, "note_count": 1000, "author_count": 100, "interaction_total": 120000},
        "chart_data": {
            "keyword_matrix": [
                {
                    "keyword": "去屑洗发水",
                    "category": "产品/品类词",
                    "note_count": 63,
                    "interaction_total": 27049,
                    "opportunity_score": 86.5,
                    "relevance_score": 90,
                    "reason": "命中品类或产品功效，和品牌经营目标相关。",
                    "recommended_action": "围绕去屑洗发水产出测评内容。",
                }
            ]
        },
        "report_sections": [
            {
                "section_id": "section-01",
                "title": "长文本表格",
                "core_judgment": "测试品牌在该维度有明确机会。",
                "evidence": ["笔记 1000 条"],
                "body": ["测试品牌在近 90 天有足够样本。"],
                "bullets": ["测试要点"],
                "table": [
                    {
                        "类型": "风险",
                        "内容": "这是一段很长的风险描述，用于验证渲染器不会把大段文字硬塞进表格单元格导致移动端撑破布局。",
                    },
                    {
                        "类型": "机会",
                        "内容": "这是一段很长的机会描述，用于验证渲染器会把长文本表格转换成证据卡片展示。",
                    },
                ],
            }
        ],
    }
    html = HtmlRenderer().render_report(report)
    assert "matrix-card" in html
    assert "相关性 90" in html
    assert "evidence-card" in html
    assert '<div class="table-wrap">' not in html
