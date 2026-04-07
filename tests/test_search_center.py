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


if __name__ == "__main__":
    unittest.main()
