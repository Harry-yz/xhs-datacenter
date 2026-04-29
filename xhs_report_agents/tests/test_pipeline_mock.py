from __future__ import annotations

from pathlib import Path

from xhs_report_agents.agents.pipeline import ReportPipeline
from xhs_report_agents.config import Settings
from xhs_report_agents.schemas import DataQuality, EvidencePack, MetricBlock, NoteEvidence


class FakeDataScout:
    def build_evidence_pack(self, **kwargs):
        return EvidencePack(
            brand=kwargs["brand"],
            category=kwargs["category"],
            core_products=kwargs["core_products"],
            aliases=[kwargs["brand"], *kwargs["core_products"]],
            competitors=kwargs["competitor_brands"],
            window_days=kwargs["window_days"],
            generated_at="2026-04-28T00:00:00",
            core_metrics=MetricBlock(note_count=1, author_count=1),
            top_notes=[NoteEvidence(evidence_id="N1", note_id="1", title="测试")],
            data_quality=DataQuality(status="limited", reasons=["metrics_sparse"]),
        )


class FakeAgent:
    def __init__(self, payload):
        self.payload = payload

    def run(self, payload, schema):
        return schema.model_validate(self.payload)


def test_pipeline_writes_outputs(tmp_path: Path):
    settings = Settings(
        deepseek_api_key="test",
        deepseek_base_url="https://example.invalid",
        deepseek_model="test-model",
        database_url="postgresql+psycopg://u:p@localhost/db",
        output_dir=tmp_path,
    )
    pipeline = ReportPipeline.__new__(ReportPipeline)
    pipeline.settings = settings
    pipeline.checkpoint = "none"
    pipeline.data_scout = FakeDataScout()
    pipeline.metric_agent = FakeAgent(
        {
            "overall_score": 50,
            "dimension_scores": [
                {"name": "声量渗透", "score": 50, "confidence": "low", "rationale": "样本少", "evidence_ids": ["N1"]}
            ],
        }
    )
    pipeline.content_agent = FakeAgent({"winning_patterns": [{"claim": "测试内容模式", "evidence_ids": ["N1"], "confidence": "low"}]})
    pipeline.audience_agent = FakeAgent({"confidence": "low", "limitations": ["评论不足"]})
    pipeline.diagnosis_agent = FakeAgent({"executive_findings": [{"claim": "样本不足", "evidence_ids": ["N1"], "confidence": "low"}]})
    pipeline.fact_check_agent = FakeAgent(
        {
            "approved_claims": [{"claim": "样本不足", "evidence_ids": ["N1"], "confidence": "low"}],
            "required_disclaimers": ["互动数据稀疏"],
        }
    )
    pipeline.executive_editor_agent = FakeAgent(
        {
            "title": "测试品牌 小红书品牌健康报告",
            "subtitle": "测试副标题",
            "executive_summary": "测试摘要",
            "key_findings": ["样本不足"],
            "management_diagnosis": "测试诊断",
        }
    )
    pipeline.external_context_agent = FakeAgent({"category_context": ["测试品类"], "platform_context": ["测试平台"]})
    pipeline.section_writer_agent = FakeAgent(
        {
            "report_sections": [
                {
                    "section_id": f"section-{i:02d}",
                    "title": f"测试章节{i}",
                    "core_judgment": "测试判断",
                    "evidence": ["N1"],
                    "body": ["测试正文"],
                    "bullets": ["测试要点"],
                    "table": [{"指标": "笔记", "值": 1}],
                }
                for i in range(1, 16)
            ]
        }
    )
    pipeline.report_writer_agent = FakeAgent({"markdown": "# 测试品牌 小红书品牌健康报告\n\n## 数据说明\n- 互动数据稀疏"})
    from xhs_report_agents.renderers.html import HtmlRenderer

    pipeline.html_renderer = HtmlRenderer()
    pipeline.use_pro_editor = True
    pipeline.use_external_context = True
    bundle = pipeline.generate(
        brand="测试品牌",
        category="测试品类",
        core_products=["测试产品"],
        competitor_brands=["测试竞品"],
        time_window=90,
        max_notes=10,
        max_comments=10,
    )
    md_path, html_path = pipeline.write_outputs(bundle, tmp_path)
    assert md_path.exists()
    assert html_path.exists()
    assert md_path.parent == tmp_path
    assert bundle.report_json["kpis"]["note_count"] == 1
    assert bundle.report_json["input_profile"]["category"] == "测试品类"
    assert bundle.report_json["input_profile"]["core_products"] == ["测试产品"]
    assert bundle.report_json["input_profile"]["competitor_brands"] == ["测试竞品"]
    assert len(bundle.report_json["report_sections"]) == 15
