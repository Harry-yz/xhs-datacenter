import unittest

from app.api import search as search_api


class SearchRecallGuardTests(unittest.TestCase):
    def test_should_use_brand_mode_for_exact_brand_alias(self) -> None:
        class _FakeBrandDB:
            def execute(self, *_args, **_kwargs):
                class _Result:
                    def first(self_inner):
                        return (1,)

                return _Result()

        self.assertTrue(
            search_api._should_use_brand_mode(
                _FakeBrandDB(),
                query="YSL",
                requested_mode="category",
                industry=None,
            )
        )

    def test_should_not_use_brand_mode_when_industry_is_selected(self) -> None:
        class _FakeBrandDB:
            def execute(self, *_args, **_kwargs):
                raise AssertionError("brand lookup should be skipped when industry is present")

        self.assertFalse(
            search_api._should_use_brand_mode(
                _FakeBrandDB(),
                query="YSL",
                requested_mode="category",
                industry="beauty",
            )
        )

    def test_should_run_recall_guard_on_low_total(self) -> None:
        original_enabled = search_api.settings.search_v2_recall_guard_enabled
        original_min_total = search_api.settings.search_v2_recall_guard_min_total
        object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", True)
        object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", 20)
        try:
            self.assertTrue(
                search_api._should_run_v2_recall_guard(
                    query="洗发水",
                    v2_result={"hit": True, "pagination": {"total": 2}},
                )
            )
        finally:
            object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", original_enabled)
            object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", original_min_total)

    def test_should_not_run_recall_guard_on_healthy_total(self) -> None:
        original_enabled = search_api.settings.search_v2_recall_guard_enabled
        original_min_total = search_api.settings.search_v2_recall_guard_min_total
        object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", True)
        object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", 20)
        try:
            self.assertFalse(
                search_api._should_run_v2_recall_guard(
                    query="洗发水",
                    v2_result={"hit": True, "pagination": {"total": 36}},
                )
            )
        finally:
            object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", original_enabled)
            object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", original_min_total)

    def test_should_run_recall_guard_on_single_page_plateau(self) -> None:
        original_enabled = search_api.settings.search_v2_recall_guard_enabled
        original_min_total = search_api.settings.search_v2_recall_guard_min_total
        object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", True)
        object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", 20)
        try:
            self.assertTrue(
                search_api._should_run_v2_recall_guard(
                    query="洗发水",
                    v2_result={"hit": True, "pagination": {"total": 30, "has_more": False}},
                    page_size=30,
                )
            )
            self.assertFalse(
                search_api._should_run_v2_recall_guard(
                    query="洗发水",
                    v2_result={"hit": True, "pagination": {"total": 30, "has_more": True}},
                    page_size=30,
                )
            )
        finally:
            object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", original_enabled)
            object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", original_min_total)

    def test_should_prefer_legacy_for_recall_guard(self) -> None:
        original_delta = search_api.settings.search_v2_recall_guard_delta
        object.__setattr__(search_api.settings, "search_v2_recall_guard_delta", 5)
        try:
            self.assertTrue(
                search_api._should_prefer_legacy_for_recall_guard(
                    v2_result={"pagination": {"total": 2}},
                    legacy_result={"pagination": {"total": 30}},
                )
            )
            self.assertFalse(
                search_api._should_prefer_legacy_for_recall_guard(
                    v2_result={"pagination": {"total": 28}},
                    legacy_result={"pagination": {"total": 30}},
                )
            )
        finally:
            object.__setattr__(search_api.settings, "search_v2_recall_guard_delta", original_delta)

    def test_should_run_recall_guard_on_deep_page_empty_result(self) -> None:
        original_enabled = search_api.settings.search_v2_recall_guard_enabled
        original_min_total = search_api.settings.search_v2_recall_guard_min_total
        object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", True)
        object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", 20)
        try:
            self.assertTrue(
                search_api._should_run_v2_recall_guard(
                    query="YSL",
                    v2_result={"hit": True, "items": [], "pagination": {"total": 420, "has_more": False}},
                    page_size=30,
                    page=15,
                )
            )
        finally:
            object.__setattr__(search_api.settings, "search_v2_recall_guard_enabled", original_enabled)
            object.__setattr__(search_api.settings, "search_v2_recall_guard_min_total", original_min_total)

    def test_should_release_pending_once_any_first_page_rows_exist(self) -> None:
        self.assertFalse(
            search_api._should_keep_pending_until_first_page_full(
                {"hit": True, "items": [{"note_id": "1"}], "pagination": {"total": 1, "has_more": False}},
                page_size=30,
            )
        )
        self.assertTrue(
            search_api._should_keep_pending_until_first_page_full(
                {"hit": False, "items": [], "pagination": {"total": 0, "has_more": False}},
                page_size=30,
            )
        )

    def test_load_active_job_syncs_stale_running_jobs(self) -> None:
        original_try_sync = search_api.try_sync_job_status_with_crawl
        original_get_job = search_api.get_search_job
        try:
            search_api.try_sync_job_status_with_crawl = lambda _db, job_id: {"job_id": job_id, "status": "ready"}
            search_api.get_search_job = lambda _db, job_id: {"job_id": job_id, "status": "running"}
            self.assertIsNone(search_api._load_active_job(object(), "job-1"))
        finally:
            search_api.try_sync_job_status_with_crawl = original_try_sync
            search_api.get_search_job = original_get_job

    def test_ready_job_with_zero_row_count_returns_pending_without_querying_search(self) -> None:
        original_try_sync = search_api.try_sync_job_status_with_crawl
        original_query_brand = search_api.query_brand_category_db_first
        original_query_brand_v2 = search_api.query_brand_category_db_first_v2
        try:
            search_api.try_sync_job_status_with_crawl = lambda _db, job_id: {
                "job_id": job_id,
                "status": "ready",
                "search_type": "brand_category",
                "query": "冷词",
                "request_payload": {"mode": "category"},
                "response_payload": {"row_count": 0, "crawl_batch_id": "batch-1"},
            }

            def _unexpected(*_args, **_kwargs):
                raise AssertionError("search query should not run for zero-row ready jobs")

            search_api.query_brand_category_db_first = _unexpected
            search_api.query_brand_category_db_first_v2 = _unexpected

            response = search_api.get_unified_search_job("job-1", page=1, size=30, db=object())
            self.assertEqual(response.data["status"], "pending")
            self.assertEqual(response.data["pending_reason"], "waiting_for_first_page")
            self.assertEqual(response.data["job_id"], "job-1")
        finally:
            search_api.try_sync_job_status_with_crawl = original_try_sync
            search_api.query_brand_category_db_first = original_query_brand
            search_api.query_brand_category_db_first_v2 = original_query_brand_v2

    def test_add_health_reasons_dedupes_and_marks_worker_unhealthy(self) -> None:
        health = search_api._add_health_reasons(
            {"healthy": True, "reasons": ["low_results"]},
            "low_results",
            "worker_unavailable",
        )
        self.assertEqual(health["reasons"], ["low_results", "worker_unavailable"])
        self.assertFalse(health["healthy"])


if __name__ == "__main__":
    unittest.main()
