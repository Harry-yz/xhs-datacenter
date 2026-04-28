from __future__ import annotations

from pathlib import Path

from xhs_report_agents.agents.base import OfflineAgent
from xhs_report_agents.graph.nodes import ReportGraphRuntime
from xhs_report_agents.graph.workflow import run_report_graph
from xhs_report_agents.renderers.html import HtmlRenderer
from xhs_report_agents.schemas import DataQuality, EvidencePack, MetricBlock, NoteEvidence


class FakeDataScout:
    def build_evidence_pack(self, **kwargs):
        return EvidencePack(
            brand=kwargs["brand"],
            aliases=[kwargs["brand"]],
            competitors=[],
            window_days=kwargs["window_days"],
            generated_at="2026-04-28T00:00:00",
            core_metrics=MetricBlock(note_count=3, author_count=2, interaction_total=12),
            top_notes=[NoteEvidence(evidence_id="N1", note_id="1", title="测试")],
            data_quality=DataQuality(status="warning", reasons=["comments_insufficient"]),
        )


def test_langgraph_offline_workflow_reaches_finalize(tmp_path: Path):
    runtime = ReportGraphRuntime(
        data_scout=FakeDataScout(),
        metric_agent=OfflineAgent(name="MetricAnalystAgent"),
        content_agent=OfflineAgent(name="ContentInsightAgent"),
        audience_agent=OfflineAgent(name="AudienceInsightAgent"),
        diagnosis_agent=OfflineAgent(name="DiagnosisAgent"),
        fact_check_agent=OfflineAgent(name="FactCheckAgent"),
        report_writer_agent=OfflineAgent(name="ReportWriterAgent"),
        executive_editor_agent=OfflineAgent(name="ExecutiveEditorAgent"),
        external_context_agent=OfflineAgent(name="ExternalContextScoutAgent"),
        section_writer_agent=OfflineAgent(name="SectionWriterAgent"),
        html_renderer=HtmlRenderer(),
        output_dir=tmp_path,
    )
    state = run_report_graph(
        runtime=runtime,
        initial_state={
            "brand": "测试品牌",
            "aliases": [],
            "competitors": [],
            "days": 90,
            "max_notes": 10,
            "max_comments": 10,
            "enable_text_fallback": False,
        },
        checkpoint="none",
    )
    assert state["fact_check"]
    assert len(state["report_json"]["report_sections"]) >= 15
    assert state["markdown_path"].endswith(".md")
    assert state["html_path"].endswith(".html")
    assert state["json_path"].endswith(".json")
    assert Path(state["markdown_path"]).exists()
    assert Path(state["html_path"]).exists()
    assert Path(state["json_path"]).exists()
