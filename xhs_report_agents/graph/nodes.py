from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

from pydantic import BaseModel

from ..data_access import DataScoutAgent
from ..report_data import ReportDataComposer
from ..renderers.html import HtmlRenderer
from ..renderers.markdown import fallback_markdown, render_report_markdown
from ..schemas import (
    AudienceInsights,
    ContentInsights,
    Diagnosis,
    EvidencePack,
    ExecutiveEditorial,
    ExternalContext,
    FactCheckResult,
    MetricAnalysis,
    MetricBlock,
    ReportBundle,
    SectionWriterOutput,
    DataQuality,
)
from .state import ReportState


class MarkdownResponse(BaseModel):
    markdown: str


class ReportGraphRuntime:
    def __init__(
        self,
        *,
        data_scout: DataScoutAgent,
        metric_agent,
        content_agent,
        audience_agent,
        diagnosis_agent,
        fact_check_agent,
        report_writer_agent,
        executive_editor_agent,
        external_context_agent,
        section_writer_agent,
        html_renderer: HtmlRenderer,
        output_dir: Path,
        use_pro_editor: bool = True,
        use_external_context: bool = True,
    ):
        self.data_scout = data_scout
        self.metric_agent = metric_agent
        self.content_agent = content_agent
        self.audience_agent = audience_agent
        self.diagnosis_agent = diagnosis_agent
        self.fact_check_agent = fact_check_agent
        self.report_writer_agent = report_writer_agent
        self.executive_editor_agent = executive_editor_agent
        self.external_context_agent = external_context_agent
        self.section_writer_agent = section_writer_agent
        self.html_renderer = html_renderer
        self.output_dir = output_dir
        self.use_pro_editor = use_pro_editor
        self.use_external_context = use_external_context
        self.composer = ReportDataComposer()

    def data_scout_node(self, state: ReportState) -> ReportState:
        try:
            pack = self.data_scout.build_evidence_pack(
                brand=state["brand"],
                category=state["category"],
                core_products=state.get("core_products", []),
                competitor_brands=state.get("competitor_brands", []),
                window_days=int(state.get("time_window", 90)),
                max_notes=int(state.get("max_notes", 1000)),
                max_comments=int(state.get("max_comments", 500)),
                enable_text_fallback=bool(state.get("enable_text_fallback", False)),
            )
            return {"evidence_pack": pack.model_dump()}
        except Exception as exc:
            pack = EvidencePack(
                brand=state["brand"],
                category=state.get("category", ""),
                core_products=state.get("core_products", []),
                aliases=[state["brand"], *state.get("core_products", [])],
                competitors=state.get("competitor_brands", []),
                window_days=int(state.get("time_window", 90)),
                generated_at=datetime.now().isoformat(timespec="seconds"),
                core_metrics=MetricBlock(),
                data_quality=DataQuality(
                    status="limited",
                    reasons=["data_scout_failed"],
                    notes=[f"数据库取数失败，报告仅保留工作流结构与可恢复状态：{type(exc).__name__}"],
                ),
            )
            return {"evidence_pack": pack.model_dump()}

    def evidence_compressor_node(self, state: ReportState) -> ReportState:
        return {"compressed_evidence": _payload(state, note_limit=60, comment_limit=300, author_limit=30)["evidence_pack"]}

    def external_context_node(self, state: ReportState) -> ReportState:
        if not self.use_external_context:
            context = ExternalContext(cautions=["external_context_disabled"])
            return {"external_context": context.model_dump()}
        try:
            context = self.external_context_agent.run(
                {
                    "evidence_pack": state.get("compressed_evidence") or _payload(state)["evidence_pack"],
                    "brand": state["brand"],
                    "category": state.get("category", ""),
                    "core_products": state.get("core_products", []),
                    "competitor_brands": state.get("competitor_brands", []),
                    "instruction": "补充小红书品牌健康度售前报告的稳健背景，不显式展示来源。",
                },
                ExternalContext,
            )
        except Exception:
            context = ExternalContext(cautions=["external_context_fallback"])
        return {"external_context": context.model_dump()}

    def metric_analyst_node(self, state: ReportState) -> ReportState:
        metric = self.metric_agent.run({**_payload(state), "external_context": state.get("external_context", {})}, MetricAnalysis)
        return {"metric_analysis": metric.model_dump()}

    def content_insight_node(self, state: ReportState) -> ReportState:
        content = self.content_agent.run(
            {**_payload(state), "external_context": state.get("external_context", {}), "metric_analysis": state["metric_analysis"]},
            ContentInsights,
        )
        return {"content_insights": content.model_dump()}

    def audience_insight_node(self, state: ReportState) -> ReportState:
        audience = self.audience_agent.run(
            {
                **_payload(state),
                "external_context": state.get("external_context", {}),
                "metric_analysis": state["metric_analysis"],
                "content_insights": state.get("content_insights", {}),
            },
            AudienceInsights,
        )
        return {"audience_insights": audience.model_dump()}

    def diagnosis_node(self, state: ReportState) -> ReportState:
        diagnosis = self.diagnosis_agent.run(
            {
                **_payload(state),
                "external_context": state.get("external_context", {}),
                "metric_analysis": state["metric_analysis"],
                "content_insights": state.get("content_insights", {}),
                "audience_insights": state.get("audience_insights", {}),
            },
            Diagnosis,
        )
        return {"diagnosis": diagnosis.model_dump()}

    def fact_check_node(self, state: ReportState) -> ReportState:
        fact_check = self.fact_check_agent.run(
            {
                **_payload(state),
                "external_context": state.get("external_context", {}),
                "metric_analysis": state["metric_analysis"],
                "content_insights": state.get("content_insights", {}),
                "audience_insights": state.get("audience_insights", {}),
                "diagnosis": state["diagnosis"],
            },
            FactCheckResult,
        )
        return {"fact_check": fact_check.model_dump()}

    def report_data_composer_node(self, state: ReportState) -> ReportState:
        if not state.get("fact_check"):
            raise RuntimeError("fact_check is required before report_data_composer")
        report_json = self.composer.compose(
            evidence=EvidencePack.model_validate(state["evidence_pack"]),
            metric=MetricAnalysis.model_validate(state["metric_analysis"]),
            content=ContentInsights.model_validate(state.get("content_insights", {})),
            audience=AudienceInsights.model_validate(state.get("audience_insights", {})),
            diagnosis=Diagnosis.model_validate(state["diagnosis"]),
            fact_check=FactCheckResult.model_validate(state["fact_check"]),
            external_context=ExternalContext.model_validate(state.get("external_context", {})),
        )
        return {"report_json": report_json}

    def executive_editor_node(self, state: ReportState) -> ReportState:
        model = getattr(self.executive_editor_agent, "model", None)
        if not self.use_pro_editor:
            editorial = ExecutiveEditorial.model_validate(state["report_json"]["editorial"])
            report_json = dict(state["report_json"])
            report_json["model_usage"] = {
                "executive_editor": {"enabled": False, "status": "disabled", "model": model}
            }
            return {
                "executive_editorial": editorial.model_dump(),
                "report_json": report_json,
                "model_usage": report_json["model_usage"],
            }
        try:
            editorial = self.executive_editor_agent.run(
                {
                    "report_json": state["report_json"],
                    "fact_check": state["fact_check"],
                },
                ExecutiveEditorial,
            )
            status = {"enabled": True, "status": "used", "model": model}
        except Exception:
            editorial = ExecutiveEditorial.model_validate(state["report_json"]["editorial"])
            status = {"enabled": True, "status": "fallback", "model": model}
        report_json = dict(state["report_json"])
        report_json["editorial"] = editorial.model_dump()
        report_json["model_usage"] = {"executive_editor": status}
        return {
            "executive_editorial": editorial.model_dump(),
            "report_json": report_json,
            "model_usage": report_json["model_usage"],
        }

    def section_writer_node(self, state: ReportState) -> ReportState:
        if not state.get("fact_check"):
            raise RuntimeError("fact_check is required before section_writer")
        model = getattr(self.section_writer_agent, "model", None)
        try:
            output = self.section_writer_agent.run(
                {
                    **_payload(state, note_limit=60, comment_limit=300, author_limit=30),
                    "metric_analysis": state["metric_analysis"],
                    "content_insights": state.get("content_insights", {}),
                    "audience_insights": state.get("audience_insights", {}),
                    "diagnosis": state["diagnosis"],
                    "fact_check": state["fact_check"],
                    "external_context": state.get("external_context", {}),
                    "executive_editorial": state.get("executive_editorial", {}),
                    "report_json": state.get("report_json", {}),
                },
                SectionWriterOutput,
            )
            status = {"enabled": True, "status": "used", "model": model}
        except Exception:
            report_json = dict(state["report_json"])
            fallback_report = self.composer.compose(
                evidence=EvidencePack.model_validate(state["evidence_pack"]),
                metric=MetricAnalysis.model_validate(state["metric_analysis"]),
                content=ContentInsights.model_validate(state.get("content_insights", {})),
                audience=AudienceInsights.model_validate(state.get("audience_insights", {})),
                diagnosis=Diagnosis.model_validate(state["diagnosis"]),
                fact_check=FactCheckResult.model_validate(state["fact_check"]),
                executive=ExecutiveEditorial.model_validate(state.get("executive_editorial", {})),
                external_context=ExternalContext.model_validate(state.get("external_context", {})),
            )
            output = SectionWriterOutput.model_validate({"report_sections": fallback_report["report_sections"]})
            status = {"enabled": True, "status": "fallback", "model": model}
        report_json = dict(state["report_json"])
        usage = dict(report_json.get("model_usage", {}))
        usage["section_writer"] = status
        report_json["model_usage"] = usage
        report_json["report_sections"] = [section.model_dump() for section in output.report_sections]
        markdown = render_report_markdown(report_json)
        return {"report_json": report_json, "markdown": markdown, "model_usage": usage}

    def report_writer_node(self, state: ReportState) -> ReportState:
        if state.get("report_json", {}).get("report_sections"):
            return {"markdown": render_report_markdown(state["report_json"])}
        response = self.report_writer_agent.run(
            {**_payload(state), "report_json": state.get("report_json", {})},
            MarkdownResponse,
        )
        return {"markdown": response.markdown.strip()}

    def html_renderer_node(self, state: ReportState) -> ReportState:
        return {"html": self.html_renderer.render_report(state["report_json"])}

    def finalize_node(self, state: ReportState) -> ReportState:
        if not state.get("fact_check"):
            raise RuntimeError("fact_check is required before finalize")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        bundle = _bundle_from_state(state)
        slug = _slug(bundle.evidence_pack.brand)
        date = bundle.generated_at.date().isoformat()
        md_path = self.output_dir / f"{slug}-xhs-brand-health-{date}.md"
        html_path = self.output_dir / f"{slug}-xhs-brand-health-{date}.html"
        json_path = self.output_dir / f"{slug}-xhs-brand-health-{date}.json"
        md_path.write_text(bundle.markdown, encoding="utf-8")
        html_path.write_text(state.get("html") or self.html_renderer.render(bundle), encoding="utf-8")
        json_path.write_text(json.dumps(state.get("report_json", {}), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown_path": str(md_path), "html_path": str(html_path), "json_path": str(json_path)}


def _payload(state: ReportState, *, note_limit: int = 30, comment_limit: int = 80, author_limit: int = 20) -> dict[str, Any]:
    evidence = dict(state["evidence_pack"])
    evidence["top_notes"] = evidence.get("top_notes", [])[:note_limit]
    evidence["comment_signals"] = evidence.get("comment_signals", [])[:comment_limit]
    evidence["top_authors"] = evidence.get("top_authors", [])[:author_limit]
    return {"evidence_pack": evidence}


def _bundle_from_state(state: ReportState) -> ReportBundle:
    return ReportBundle(
        evidence_pack=EvidencePack.model_validate(state["evidence_pack"]),
        metric_analysis=MetricAnalysis.model_validate(state["metric_analysis"]),
        content_insights=ContentInsights.model_validate(state.get("content_insights", {})),
        audience_insights=AudienceInsights.model_validate(state.get("audience_insights", {})),
        diagnosis=Diagnosis.model_validate(state["diagnosis"]),
        fact_check=FactCheckResult.model_validate(state["fact_check"]),
        markdown=state["markdown"],
        report_json=state.get("report_json", {}),
        executive_editorial=ExecutiveEditorial.model_validate(state["executive_editorial"]) if state.get("executive_editorial") else None,
        external_context=ExternalContext.model_validate(state["external_context"]) if state.get("external_context") else None,
    )


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "brand"
