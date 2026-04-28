from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import Settings
from ..data_access import DataScoutAgent, create_readonly_engine
from ..graph.nodes import ReportGraphRuntime
from ..graph.workflow import run_report_graph
from ..llm_client import DeepSeekClient
from ..prompts import (
    AUDIENCE_INSIGHT,
    CONTENT_INSIGHT,
    DIAGNOSIS,
    EXECUTIVE_EDITOR,
    EXTERNAL_CONTEXT,
    FACT_CHECK,
    METRIC_ANALYST,
    REPORT_WRITER,
    SECTION_WRITER,
)
from ..renderers.html import HtmlRenderer
from ..renderers.markdown import fallback_markdown
from ..schemas import (
    ReportBundle,
)
from .base import JsonAgent, OfflineAgent


class ReportPipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        offline: bool = False,
        checkpoint: str = "memory",
        use_pro_editor: bool = True,
        use_external_context: bool = True,
    ):
        self.settings = settings
        self.engine = create_readonly_engine(settings.database_url)
        self.data_scout = DataScoutAgent(self.engine)
        self.offline = offline
        self.checkpoint = checkpoint
        self.use_pro_editor = use_pro_editor
        self.use_external_context = use_external_context
        if offline:
            self.client = None
            self.metric_agent = OfflineAgent(name="MetricAnalystAgent")
            self.content_agent = OfflineAgent(name="ContentInsightAgent")
            self.audience_agent = OfflineAgent(name="AudienceInsightAgent")
            self.diagnosis_agent = OfflineAgent(name="DiagnosisAgent")
            self.fact_check_agent = OfflineAgent(name="FactCheckAgent")
            self.report_writer_agent = OfflineAgent(name="ReportWriterAgent")
            self.executive_editor_agent = OfflineAgent(name="ExecutiveEditorAgent")
            self.external_context_agent = OfflineAgent(name="ExternalContextScoutAgent")
            self.section_writer_agent = OfflineAgent(name="SectionWriterAgent")
        else:
            self.client = DeepSeekClient(settings)
            self.metric_agent = JsonAgent(name="MetricAnalystAgent", prompt=METRIC_ANALYST, client=self.client, model=settings.deepseek_pro_model)
            self.content_agent = JsonAgent(name="ContentInsightAgent", prompt=CONTENT_INSIGHT, client=self.client, model=settings.deepseek_pro_model)
            self.audience_agent = JsonAgent(name="AudienceInsightAgent", prompt=AUDIENCE_INSIGHT, client=self.client, model=settings.deepseek_pro_model)
            self.diagnosis_agent = JsonAgent(name="DiagnosisAgent", prompt=DIAGNOSIS, client=self.client, model=settings.deepseek_pro_model)
            self.fact_check_agent = JsonAgent(name="FactCheckAgent", prompt=FACT_CHECK, client=self.client, model=settings.deepseek_fast_model)
            self.report_writer_agent = JsonAgent(name="ReportWriterAgent", prompt=REPORT_WRITER, client=self.client, model=settings.deepseek_fast_model)
            self.executive_editor_agent = JsonAgent(name="ExecutiveEditorAgent", prompt=EXECUTIVE_EDITOR, client=self.client, model=settings.deepseek_pro_model)
            self.external_context_agent = JsonAgent(name="ExternalContextScoutAgent", prompt=EXTERNAL_CONTEXT, client=self.client, model=settings.deepseek_fast_model)
            self.section_writer_agent = JsonAgent(name="SectionWriterAgent", prompt=SECTION_WRITER, client=self.client, model=settings.deepseek_pro_model)
        self.html_renderer = HtmlRenderer()

    def generate(
        self,
        *,
        brand: str,
        aliases: list[str],
        competitors: list[str],
        days: int,
        max_notes: int,
        max_comments: int,
        enable_text_fallback: bool = False,
        use_external_context: bool | None = None,
    ) -> ReportBundle:
        runtime = ReportGraphRuntime(
            data_scout=self.data_scout,
            metric_agent=self.metric_agent,
            content_agent=self.content_agent,
            audience_agent=self.audience_agent,
            diagnosis_agent=self.diagnosis_agent,
            fact_check_agent=self.fact_check_agent,
            report_writer_agent=self.report_writer_agent,
            executive_editor_agent=self.executive_editor_agent,
            external_context_agent=self.external_context_agent,
            section_writer_agent=self.section_writer_agent,
            html_renderer=self.html_renderer,
            output_dir=self.settings.output_dir,
            use_pro_editor=self.use_pro_editor,
            use_external_context=self.use_external_context if use_external_context is None else use_external_context,
        )
        final_state = run_report_graph(
            runtime=runtime,
            initial_state={
                "brand": brand,
                "aliases": aliases,
                "competitors": competitors,
                "days": days,
                "max_notes": max_notes,
                "max_comments": max_comments,
                "enable_text_fallback": enable_text_fallback,
                "use_external_context": self.use_external_context if use_external_context is None else use_external_context,
            },
            checkpoint=self.checkpoint,  # type: ignore[arg-type]
        )
        return ReportBundle(
            evidence_pack=final_state["evidence_pack"],
            metric_analysis=final_state["metric_analysis"],
            content_insights=final_state.get("content_insights", {}),
            audience_insights=final_state.get("audience_insights", {}),
            diagnosis=final_state["diagnosis"],
            fact_check=final_state["fact_check"],
            markdown=final_state["markdown"],
            report_json=final_state.get("report_json", {}),
            executive_editorial=final_state.get("executive_editorial"),
            external_context=final_state.get("external_context"),
        )

    def write_outputs(self, bundle: ReportBundle, output_dir: Path | None = None) -> tuple[Path, Path]:
        out = output_dir or self.settings.output_dir
        out.mkdir(parents=True, exist_ok=True)
        slug = _slug(bundle.evidence_pack.brand)
        date = bundle.generated_at.date().isoformat()
        md_path = out / f"{slug}-xhs-brand-health-{date}.md"
        html_path = out / f"{slug}-xhs-brand-health-{date}.html"
        if not md_path.exists():
            md_path.write_text(bundle.markdown, encoding="utf-8")
        if not html_path.exists():
            html_path.write_text(self.html_renderer.render(bundle), encoding="utf-8")
        return md_path, html_path


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "brand"
