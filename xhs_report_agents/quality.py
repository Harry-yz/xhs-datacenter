from __future__ import annotations

from typing import Any


GENERIC_SECTION_SENTENCES = (
    "用于建立售前讨论的主线",
    "用于把诊断转成可执行方向",
    "报告不把平台当作单纯曝光渠道",
    "售前阶段不展开完整 SOP",
)

WEAK_KEYWORDS = {"未标注", "电脑", "软装", "运动", "彩妆", "面霜"}


class ReportQualityGate:
    def evaluate(self, report: dict[str, Any]) -> list[dict[str, str]]:
        warnings: list[dict[str, str]] = []
        warnings.extend(self._keyword_warnings(report.get("keyword_opportunity_matrix", [])))
        warnings.extend(self._section_warnings(report.get("report_sections", [])))
        return warnings

    def _keyword_warnings(self, rows: Any) -> list[dict[str, str]]:
        if not isinstance(rows, list):
            return [{"type": "keyword_matrix", "message": "keyword_opportunity_matrix is not a list"}]
        top_rows = [row for row in rows[:8] if isinstance(row, dict)]
        warnings: list[dict[str, str]] = []
        saturated = [
            row for row in top_rows
            if _float(row.get("opportunity_score")) >= 99
        ]
        if len(saturated) >= max(3, len(top_rows) // 2):
            warnings.append(
                {
                    "type": "keyword_score_saturation",
                    "message": "Top keyword opportunity scores are saturated near 100",
                }
            )
        weak = [
            str(row.get("keyword") or row.get("search_keyword") or "")
            for row in top_rows
            if str(row.get("keyword") or row.get("search_keyword") or "") in WEAK_KEYWORDS
            and str(row.get("category") or "") in {"", "泛搜索词", "弱相关词", "机会词"}
        ]
        if weak:
            warnings.append(
                {
                    "type": "weak_keyword_in_top",
                    "message": "Weak keywords appeared in top opportunities: " + ", ".join(weak),
                }
            )
        return warnings

    def _section_warnings(self, sections: Any) -> list[dict[str, str]]:
        if not isinstance(sections, list):
            return [{"type": "sections", "message": "report_sections is not a list"}]
        warnings: list[dict[str, str]] = []
        seen_judgments: set[str] = set()
        for idx, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                continue
            sid = str(section.get("section_id") or f"section-{idx:02d}")
            judgment = str(section.get("core_judgment") or "").strip()
            if judgment and judgment in seen_judgments:
                warnings.append({"type": "duplicate_judgment", "message": f"{sid} repeats a core judgment"})
            if judgment:
                seen_judgments.add(judgment)
            text = " ".join(
                [judgment]
                + [str(x) for x in section.get("body", []) if x]
                + [str(x) for x in section.get("bullets", []) if x]
            )
            for sentence in GENERIC_SECTION_SENTENCES:
                if sentence in text:
                    warnings.append({"type": "generic_copy", "message": f"{sid} contains generic template copy"})
                    break
            table = section.get("table") or []
            if isinstance(table, list):
                for row in table[:12]:
                    if not isinstance(row, dict):
                        continue
                    for value in row.values():
                        if len(str(value)) > 120:
                            warnings.append({"type": "long_table_cell", "message": f"{sid} has long table content"})
                            return warnings
        return warnings


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
