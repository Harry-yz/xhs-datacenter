import unittest
from datetime import datetime, timezone

from app.services import search_center
from app.services.search_intent import split_intent_terms


class SearchIntentEngineTests(unittest.TestCase):
    def test_split_intent_terms_expands_industry_term(self) -> None:
        terms = split_intent_terms("美妆个护")
        self.assertIn("美妆个护", terms)
        self.assertIn("美妆", terms)
        self.assertIn("护肤", terms)
        self.assertIn("个护", terms)

    def test_split_intent_terms_filters_stop_words_from_long_sentence(self) -> None:
        terms = split_intent_terms("适合熬夜的护肤品推荐", max_terms=20)
        self.assertIn("熬夜", terms)
        self.assertTrue(any(token in terms for token in ("护肤品", "护肤")))
        self.assertNotIn("适合", terms)
        self.assertNotIn("的", terms)
        self.assertNotIn("推荐", terms)

    def test_split_intent_terms_is_deduped_and_capped(self) -> None:
        terms = split_intent_terms("防晒 防晒 sunscreen 防晒", max_terms=4)
        self.assertLessEqual(len(terms), 4)
        lowered = [item.casefold() for item in terms]
        self.assertEqual(len(lowered), len(set(lowered)))

    def test_build_fetch_decision_respects_force_refresh(self) -> None:
        result = {
            "pagination": {"total": 120},
            "freshness": datetime.now(timezone.utc).isoformat(),
        }
        decision = search_center.build_fetch_decision(
            result=result,
            force_refresh=True,
            min_results=20,
            stale_hours=24,
        )
        self.assertTrue(decision["need_fetch"])
        self.assertIn("force_refresh", decision["reasons"])

    def test_build_fetch_decision_triggers_on_low_results(self) -> None:
        result = {
            "pagination": {"total": 8},
            "freshness": datetime.now(timezone.utc).isoformat(),
        }
        decision = search_center.build_fetch_decision(
            result=result,
            force_refresh=False,
            min_results=20,
            stale_hours=24,
        )
        self.assertTrue(decision["need_fetch"])
        self.assertIn("low_results", decision["reasons"])


if __name__ == "__main__":
    unittest.main()
