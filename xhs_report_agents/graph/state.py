from __future__ import annotations

from typing import Any, TypedDict


class ReportState(TypedDict, total=False):
    brand: str
    category: str
    core_products: list[str]
    competitor_brands: list[str]
    time_window: int
    max_notes: int
    max_comments: int
    enable_text_fallback: bool
    use_external_context: bool
    evidence_pack: dict[str, Any]
    compressed_evidence: dict[str, Any]
    external_context: dict[str, Any]
    metric_analysis: dict[str, Any]
    content_insights: dict[str, Any]
    audience_insights: dict[str, Any]
    diagnosis: dict[str, Any]
    fact_check: dict[str, Any]
    executive_editorial: dict[str, Any]
    report_json: dict[str, Any]
    model_usage: dict[str, Any]
    markdown: str
    html: str
    markdown_path: str
    html_path: str
    json_path: str
    node_errors: list[dict[str, str]]
