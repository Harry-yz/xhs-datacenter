from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DataQuality(BaseModel):
    status: Literal["ok", "warning", "limited"] = "ok"
    reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MetricBlock(BaseModel):
    note_count: int = 0
    author_count: int = 0
    like_total: int = 0
    comment_total: int = 0
    collection_total: int = 0
    share_total: int = 0
    interaction_total: int = 0
    avg_interaction: float = 0.0
    avg_collection: float = 0.0


class NoteEvidence(BaseModel):
    evidence_id: str
    note_id: str
    sample_group: str = "top_interaction"
    title: str = ""
    content_excerpt: str = ""
    author_nickname: str = ""
    publish_time: str | None = None
    post_url: str = ""
    like_count: int = 0
    comment_count: int = 0
    collection_count: int = 0
    share_count: int = 0
    interaction_total: int = 0
    tags: list[str] = Field(default_factory=list)


class AuthorEvidence(BaseModel):
    evidence_id: str
    author_id: str = ""
    author_nickname: str = ""
    note_count: int = 0
    fans_count: int = 0
    interaction_total: int = 0


class CommentEvidence(BaseModel):
    evidence_id: str
    parent_note_id: str
    comment_text: str
    comment_likes: int = 0
    comment_sentiment: str | None = None


class CompetitorMetric(BaseModel):
    brand: str
    aliases: list[str] = Field(default_factory=list)
    metrics: MetricBlock


class EvidencePack(BaseModel):
    brand: str
    category: str = ""
    core_products: list[str] = Field(default_factory=list)
    aliases: list[str]
    competitors: list[str]
    window_days: int
    generated_at: str
    core_metrics: MetricBlock
    competitor_metrics: list[CompetitorMetric] = Field(default_factory=list)
    top_notes: list[NoteEvidence] = Field(default_factory=list)
    top_authors: list[AuthorEvidence] = Field(default_factory=list)
    keyword_signals: list[dict[str, Any]] = Field(default_factory=list)
    comment_signals: list[CommentEvidence] = Field(default_factory=list)
    data_quality: DataQuality


class DimensionScore(BaseModel):
    name: str
    score: float
    confidence: Literal["high", "medium", "low"] = "medium"
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> str:
        return _confidence_label(value)


class Claim(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> str:
        return _confidence_label(value)


class MetricAnalysis(BaseModel):
    overall_score: float
    dimension_scores: list[DimensionScore]
    benchmark_gap: list[str] = Field(default_factory=list)
    metric_findings: list[Claim] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    @field_validator("benchmark_gap", "risks", mode="before")
    @classmethod
    def _coerce_string_list(cls, value: object) -> list[str]:
        return _string_list(value)


class ContentInsights(BaseModel):
    content_clusters: list[dict[str, Any]] = Field(default_factory=list)
    winning_patterns: list[Claim] = Field(default_factory=list)
    underused_topics: list[str] = Field(default_factory=list)
    search_keyword_opportunities: list[str] = Field(default_factory=list)
    content_formulas: list[str] = Field(default_factory=list)

    @field_validator("content_clusters", mode="before")
    @classmethod
    def _coerce_content_clusters(cls, value: object) -> list[dict[str, Any]]:
        return _dict_list(value, default_key="name")

    @field_validator("winning_patterns", mode="before")
    @classmethod
    def _coerce_winning_patterns(cls, value: object) -> list[dict[str, Any]]:
        return _claim_list(value)

    @field_validator("underused_topics", "search_keyword_opportunities", "content_formulas", mode="before")
    @classmethod
    def _coerce_content_string_lists(cls, value: object) -> list[str]:
        return _string_list(value)


class AudienceInsights(BaseModel):
    audience_segments: list[dict[str, Any]] = Field(default_factory=list)
    purchase_motivations: list[Claim] = Field(default_factory=list)
    pain_points: list[Claim] = Field(default_factory=list)
    usage_scenarios: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)

    @field_validator("audience_segments", mode="before")
    @classmethod
    def _coerce_audience_segments(cls, value: object) -> list[dict[str, Any]]:
        return _dict_list(value, default_key="name")

    @field_validator("purchase_motivations", "pain_points", mode="before")
    @classmethod
    def _coerce_audience_claims(cls, value: object) -> list[dict[str, Any]]:
        return _claim_list(value)

    @field_validator("usage_scenarios", "limitations", mode="before")
    @classmethod
    def _coerce_audience_string_lists(cls, value: object) -> list[str]:
        return _string_list(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> str:
        return _confidence_label(value)


class Diagnosis(BaseModel):
    executive_findings: list[Claim] = Field(default_factory=list)
    health_diagnosis: dict[str, Any] = Field(default_factory=dict)
    main_strengths: list[str] = Field(default_factory=list)
    main_weaknesses: list[str] = Field(default_factory=list)
    next_90_days_targets: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)

    @field_validator("health_diagnosis", mode="before")
    @classmethod
    def _coerce_health_diagnosis(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        text = _string_item(value)
        return {"summary": text} if text else {}

    @field_validator("executive_findings", mode="before")
    @classmethod
    def _coerce_executive_findings(cls, value: object) -> list[dict[str, Any]]:
        return _claim_list(value)

    @field_validator("main_strengths", "main_weaknesses", "next_90_days_targets", "priority_actions", mode="before")
    @classmethod
    def _coerce_diagnosis_string_lists(cls, value: object) -> list[str]:
        return _string_list(value)


class FactCheckResult(BaseModel):
    approved_claims: list[Claim] = Field(default_factory=list)
    downgraded_claims: list[Claim] = Field(default_factory=list)
    removed_claims: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)

    @field_validator("approved_claims", "downgraded_claims", mode="before")
    @classmethod
    def _coerce_fact_check_claims(cls, value: object) -> list[dict[str, Any]]:
        return _claim_list(value)

    @field_validator("removed_claims", "required_disclaimers", mode="before")
    @classmethod
    def _coerce_fact_check_string_lists(cls, value: object) -> list[str]:
        return _string_list(value)


class ExecutiveEditorial(BaseModel):
    title: str = ""
    subtitle: str = ""
    executive_summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    management_diagnosis: str = ""
    closing_note: str = ""

    @field_validator("key_findings", mode="before")
    @classmethod
    def _coerce_key_findings(cls, value: object) -> list[str]:
        return _string_list(value)


class ExternalContext(BaseModel):
    category_context: list[str] = Field(default_factory=list)
    platform_context: list[str] = Field(default_factory=list)
    brand_context: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)

    @field_validator("category_context", "platform_context", "brand_context", "cautions", mode="before")
    @classmethod
    def _coerce_context_lists(cls, value: object) -> list[str]:
        return _string_list(value)


class ReportSection(BaseModel):
    section_id: str
    title: str
    eyebrow: str = ""
    core_judgment: str = ""
    evidence: list[str] = Field(default_factory=list)
    body: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    table: list[dict[str, Any]] = Field(default_factory=list)
    cards: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("evidence", "body", "bullets", mode="before")
    @classmethod
    def _coerce_section_string_lists(cls, value: object) -> list[str]:
        return _string_list(value)

    @field_validator("table", "cards", mode="before")
    @classmethod
    def _coerce_section_dict_lists(cls, value: object) -> list[dict[str, Any]]:
        return _dict_list(value, default_key="label")


class SectionWriterOutput(BaseModel):
    report_sections: list[ReportSection]

    @field_validator("report_sections", mode="before")
    @classmethod
    def _coerce_sections(cls, value: object) -> list[dict[str, Any]]:
        return _dict_list(value, default_key="title")


class ReportBundle(BaseModel):
    evidence_pack: EvidencePack
    metric_analysis: MetricAnalysis
    content_insights: ContentInsights
    audience_insights: AudienceInsights
    diagnosis: Diagnosis
    fact_check: FactCheckResult
    markdown: str
    report_json: dict[str, Any] = Field(default_factory=dict)
    executive_editorial: ExecutiveEditorial | None = None
    external_context: ExternalContext | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


def _confidence_label(value: object) -> str:
    if value in ("high", "medium", "low"):
        return str(value)
    if isinstance(value, (int, float)):
        if value >= 0.75:
            return "high"
        if value >= 0.45:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    if text in {"高", "high", "strong"}:
        return "high"
    if text in {"低", "low", "weak"}:
        return "low"
    return "medium"


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_string_item(item) for item in value if _string_item(item)]
    item = _string_item(value)
    return [item] if item else []


def _string_item(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("description", "claim", "summary", "rationale", "name"):
            if value.get(key):
                return str(value[key]).strip()
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v)
    return str(value).strip()


def _dict_list(value: object, *, default_key: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(item)
        else:
            text = _string_item(item)
            if text:
                out.append({default_key: text})
    return out


def _claim_list(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            if "claim" not in item:
                claim = _string_item(item)
                item = {**item, "claim": claim}
            out.append(item)
        else:
            text = _string_item(item)
            if text:
                out.append({"claim": text, "evidence_ids": [], "confidence": "medium"})
    return out
