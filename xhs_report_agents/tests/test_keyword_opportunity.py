from __future__ import annotations

from xhs_report_agents.quality import ReportQualityGate
from xhs_report_agents.report_data import _keyword_opportunity_matrix


def test_keyword_opportunity_matrix_filters_weak_terms_and_avoids_saturation():
    rows = _keyword_opportunity_matrix(
        [
            {"type": "keyword", "search_keyword": "海飞丝", "note_count": 611, "interaction_total": 68784},
            {"type": "keyword", "search_keyword": "洗发水", "note_count": 19, "interaction_total": 22773},
            {"type": "keyword", "search_keyword": "去屑洗发水", "note_count": 63, "interaction_total": 27049},
            {"type": "keyword", "search_keyword": "头皮控油", "note_count": 8, "interaction_total": 5800},
            {"type": "keyword", "search_keyword": "电脑", "note_count": 1, "interaction_total": 9000},
            {"type": "keyword", "search_keyword": "软装", "note_count": 1, "interaction_total": 8000},
            {"type": "keyword", "search_keyword": "未标注", "note_count": 1, "interaction_total": 7000},
        ],
        ["头皮控油", "去屑洗发水"],
        brand="海飞丝",
        category="洗护发与去屑头皮护理",
        core_products=["去屑洗发水", "头皮护理", "洗发露"],
    )

    top_keywords = [row["keyword"] for row in rows[:5]]
    assert "电脑" not in top_keywords
    assert "软装" not in top_keywords
    assert "未标注" not in top_keywords
    assert any(row["keyword"] == "去屑洗发水" for row in rows)
    assert all(row["opportunity_score"] < 100 for row in rows[:8])
    assert len({row["opportunity_score"] for row in rows[:4]}) > 1
    assert all("relevance_score" in row and "reason" in row and "recommended_action" in row for row in rows)


def test_quality_gate_flags_keyword_saturation():
    warnings = ReportQualityGate().evaluate(
        {
            "keyword_opportunity_matrix": [
                {"keyword": f"词{i}", "opportunity_score": 100}
                for i in range(8)
            ],
            "report_sections": [],
        }
    )
    assert any(item["type"] == "keyword_score_saturation" for item in warnings)
