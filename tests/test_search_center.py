import unittest
from datetime import datetime, timedelta, timezone

from app.services import search_center


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return _FakeScalarResult(self.rows)


class _FakeMappingRowsResult:
    def __init__(self, rows=None, scalar_value=0):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar_value


class SearchCenterTests(unittest.TestCase):
    def test_category_order_clause_defaults_to_interaction(self) -> None:
        clause = search_center._category_order_clause("stat", "desc")
        self.assertIn("interaction_total", clause)
        self.assertTrue(clause.startswith("COALESCE("))
        self.assertIn(" DESC", clause)

    def test_category_order_clause_maps_like(self) -> None:
        clause = search_center._category_order_clause("like", "asc")
        self.assertEqual(clause, "COALESCE(f.like_count, 0) ASC, COALESCE(f.publish_time, f.updated_at, f.created_at) DESC")

    def test_creator_order_clause_maps_followers(self) -> None:
        clause = search_center._creator_order_clause("followers", "desc")
        self.assertIn("COALESCE(NULLIF(COALESCE(a.fans_count, an.fans_count), 0)", clause)
        self.assertIn(" DESC", clause)

    def test_expand_query_terms_merges_synonyms_and_dedupes(self) -> None:
        db = _FakeDB(["sunscreen", "防晒", "SPF"])
        terms = search_center._expand_query_terms(db, "防晒")
        self.assertEqual(terms, ["防晒", "sunscreen", "SPF"])

    def test_to_like_patterns_wraps_wildcards(self) -> None:
        self.assertEqual(search_center._to_like_patterns(["防晒", "sunscreen"]), ["%防晒%", "%sunscreen%"])

    def test_domain_expand_terms_for_industry_phrase(self) -> None:
        terms = search_center._domain_expand_terms("美妆个护")
        self.assertIn("美妆", terms)
        self.assertIn("护肤", terms)
        self.assertIn("精华", terms)

    def test_evaluate_result_health_marks_low_results(self) -> None:
        health = search_center.evaluate_result_health(
            {
                "pagination": {"total": 8},
                "freshness": datetime.now(timezone.utc).isoformat(),
            },
            min_results=30,
            stale_hours=24,
            now=datetime.now(timezone.utc),
        )
        self.assertFalse(health["healthy"])
        self.assertIn("low_results", health["reasons"])

    def test_evaluate_result_health_marks_stale_data(self) -> None:
        stale = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        health = search_center.evaluate_result_health(
            {"pagination": {"total": 100}, "freshness": stale},
            min_results=30,
            stale_hours=24,
            now=datetime.now(timezone.utc),
        )
        self.assertFalse(health["healthy"])
        self.assertIn("stale_data", health["reasons"])

    def test_evaluate_result_health_supports_sub_hour_stale_threshold(self) -> None:
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(minutes=40)).isoformat()
        health = search_center.evaluate_result_health(
            {"pagination": {"total": 100}, "freshness": stale},
            min_results=10,
            stale_hours=0.5,
            now=now,
        )
        self.assertFalse(health["healthy"])
        self.assertIn("stale_data", health["reasons"])

    def test_get_term_rel_coverage_stats(self) -> None:
        class _FakeMappingResult:
            def mappings(self):
                return self

            def first(self):
                return {
                    "note_total": 1000,
                    "term_note_total": 250,
                    "change_log_pending": 321,
                }

        class _FakeMappingDB:
            def execute(self, *_args, **_kwargs):
                return _FakeMappingResult()

        original = search_center.ensure_search_tables
        search_center.ensure_search_tables = lambda _db: None
        try:
            stats = search_center.get_term_rel_coverage_stats(_FakeMappingDB())
        finally:
            search_center.ensure_search_tables = original

        self.assertEqual(stats["note_total"], 1000)
        self.assertEqual(stats["term_note_total"], 250)
        self.assertEqual(stats["change_log_pending"], 321)
        self.assertAlmostEqual(stats["coverage_ratio"], 0.25)

    def test_bootstrap_search_runtime_marks_bootstrap_done(self) -> None:
        original_done = search_center._search_bootstrap_done
        original_ensure = search_center.ensure_search_tables
        try:
            search_center._search_bootstrap_done = False
            search_center.ensure_search_tables = lambda _db: setattr(search_center, "_search_bootstrap_done", True)
            search_center.bootstrap_search_runtime()
            self.assertTrue(search_center._search_bootstrap_done)
        finally:
            search_center._search_bootstrap_done = original_done
            search_center.ensure_search_tables = original_ensure

    def test_brand_category_v2_fast_count_skips_second_count_query(self) -> None:
        class _FastCountDB:
            def __init__(self):
                self.calls = 0

            def execute(self, *_args, **_kwargs):
                self.calls += 1
                rows = [{"note_id": f"n{i}", "title": "t", "author_id": "a"} for i in range(31)]
                return _FakeMappingRowsResult(rows=rows, scalar_value=999)

        db = _FastCountDB()
        original_expand = search_center._expand_query_terms
        original_resolve = search_center.resolve_industry_key
        try:
            search_center._expand_query_terms = lambda *_args, **_kwargs: ["防晒"]
            search_center.resolve_industry_key = lambda *_args, **_kwargs: None
            result = search_center.query_brand_category_db_first_v2(
                db,  # type: ignore[arg-type]
                query="防晒",
                mode="category",
                industry=None,
                min_like=0,
                date_range=30,
                page=1,
                size=30,
                freshness_hours=24,
                fast_count=True,
            )
        finally:
            search_center._expand_query_terms = original_expand
            search_center.resolve_industry_key = original_resolve

        self.assertEqual(db.calls, 1)
        self.assertTrue(result["pagination"]["has_more"])
        self.assertEqual(result["pagination"]["total"], 31)

    def test_brand_category_v2_exact_count_keeps_second_count_query(self) -> None:
        class _ExactCountDB:
            def __init__(self):
                self.calls = 0

            def execute(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    rows = [{"note_id": "n1", "title": "t", "author_id": "a"}]
                    return _FakeMappingRowsResult(rows=rows)
                return _FakeMappingRowsResult(scalar_value=42)

        db = _ExactCountDB()
        original_expand = search_center._expand_query_terms
        original_resolve = search_center.resolve_industry_key
        try:
            search_center._expand_query_terms = lambda *_args, **_kwargs: ["防晒"]
            search_center.resolve_industry_key = lambda *_args, **_kwargs: None
            result = search_center.query_brand_category_db_first_v2(
                db,  # type: ignore[arg-type]
                query="防晒",
                mode="category",
                industry=None,
                min_like=0,
                date_range=30,
                page=1,
                size=30,
                freshness_hours=24,
                fast_count=False,
            )
        finally:
            search_center._expand_query_terms = original_expand
            search_center.resolve_industry_key = original_resolve

        self.assertEqual(db.calls, 2)
        self.assertEqual(result["pagination"]["total"], 42)


if __name__ == "__main__":
    unittest.main()
