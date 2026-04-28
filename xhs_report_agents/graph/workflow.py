from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from .nodes import ReportGraphRuntime
from .state import ReportState


class GraphUnavailableError(RuntimeError):
    pass


def run_report_graph(
    *,
    runtime: ReportGraphRuntime,
    initial_state: ReportState,
    checkpoint: Literal["memory", "sqlite", "none"] = "memory",
    checkpoint_path: Path | None = None,
) -> ReportState:
    config = {"configurable": {"thread_id": f"xhs-report-{uuid4()}"}}
    checkpointer = _checkpointer(checkpoint, checkpoint_path)
    if hasattr(checkpointer, "__enter__"):
        with checkpointer as saver:
            graph = _compile_graph(runtime, checkpointer=saver)
            return graph.invoke(initial_state, config=config)
    graph = _compile_graph(runtime, checkpointer=checkpointer)
    return graph.invoke(initial_state, config=config)


def _compile_graph(
    runtime: ReportGraphRuntime,
    *,
    checkpointer,
):
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise GraphUnavailableError(
            "LangGraph is not installed. Install isolated dependency with: "
            "/opt/xhs_data_center/.venv/bin/pip install -r /opt/xhs_data_center/xhs_report_agents/requirements.txt"
        ) from exc

    builder = StateGraph(ReportState)
    builder.add_node("data_scout", runtime.data_scout_node)
    builder.add_node("evidence_compressor", runtime.evidence_compressor_node)
    builder.add_node("external_context", runtime.external_context_node)
    builder.add_node("metric_analyst", runtime.metric_analyst_node)
    builder.add_node("content_insight", runtime.content_insight_node)
    builder.add_node("audience_insight", runtime.audience_insight_node)
    builder.add_node("diagnosis", runtime.diagnosis_node)
    builder.add_node("fact_check", runtime.fact_check_node)
    builder.add_node("report_data_composer", runtime.report_data_composer_node)
    builder.add_node("executive_editor", runtime.executive_editor_node)
    builder.add_node("section_writer", runtime.section_writer_node)
    builder.add_node("html_renderer", runtime.html_renderer_node)
    builder.add_node("finalize", runtime.finalize_node)

    builder.add_edge(START, "data_scout")
    builder.add_edge("data_scout", "evidence_compressor")
    builder.add_edge("evidence_compressor", "external_context")
    builder.add_edge("external_context", "metric_analyst")
    builder.add_edge("metric_analyst", "content_insight")
    builder.add_edge("metric_analyst", "audience_insight")
    builder.add_edge("content_insight", "diagnosis")
    builder.add_edge("audience_insight", "diagnosis")
    builder.add_edge("diagnosis", "fact_check")
    builder.add_edge("fact_check", "report_data_composer")
    builder.add_edge("report_data_composer", "executive_editor")
    builder.add_edge("executive_editor", "section_writer")
    builder.add_edge("section_writer", "html_renderer")
    builder.add_edge("html_renderer", "finalize")
    builder.add_edge("finalize", END)

    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)


def _checkpointer(checkpoint: Literal["memory", "sqlite", "none"], checkpoint_path: Path | None):
    if checkpoint == "none":
        return None
    if checkpoint == "memory":
        try:
            from langgraph.checkpoint.memory import MemorySaver
        except Exception as exc:  # pragma: no cover
            raise GraphUnavailableError("LangGraph MemorySaver is unavailable") from exc
        return MemorySaver()
    if checkpoint == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except Exception as exc:  # pragma: no cover
            raise GraphUnavailableError(
                "SQLite checkpoint requires langgraph sqlite checkpoint package. "
                "Install a LangGraph distribution that provides langgraph.checkpoint.sqlite."
            ) from exc
        path = checkpoint_path or Path("/opt/xhs_data_center/xhs_report_agents/outputs/checkpoints.sqlite")
        path.parent.mkdir(parents=True, exist_ok=True)
        return SqliteSaver.from_conn_string(str(path))
    raise ValueError(f"Unsupported checkpoint mode: {checkpoint}")
