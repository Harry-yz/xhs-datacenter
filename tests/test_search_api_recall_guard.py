import unittest
from datetime import datetime, timezone

from app.api import search as search_api
from app.schemas import BrandCategorySearchRequest


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

    def test_running_job_returns_partial_rows_without_waiting_for_full_page(self) -> None:
        original_try_sync = search_api.try_sync_job_status_with_crawl
        original_partial = search_api._build_partial_job_result
        try:
            search_api.try_sync_job_status_with_crawl = lambda _db, job_id: {
                "job_id": job_id,
                "status": "running",
                "search_type": "brand_category",
                "query": "防晒",
                "task_id": "task-1",
                "crawl_batch_id": "batch-1",
                "request_payload": {"mode": "category"},
            }
            search_api._build_partial_job_result = lambda _db, job, page, size: {
                "hit": True,
                "items": [{"note_id": "n1"}],
                "summary": {"note_count": 1},
                "pagination": {"total": 1, "page": page, "size": size, "has_more": False},
                "freshness": datetime.now(timezone.utc).isoformat(),
            }
            response = search_api.get_unified_search_job("job-1", page=1, size=30, db=object())
            self.assertEqual(response.data["status"], "pending")
            self.assertEqual(response.data["pending_reason"], "partial_ready")
            self.assertEqual(len(response.data["items"]), 1)
        finally:
            search_api.try_sync_job_status_with_crawl = original_try_sync
            search_api._build_partial_job_result = original_partial

    def test_add_health_reasons_dedupes_and_marks_worker_unhealthy(self) -> None:
        health = search_api._add_health_reasons(
            {"healthy": True, "reasons": ["low_results"]},
            "low_results",
            "worker_unavailable",
        )
        self.assertEqual(health["reasons"], ["low_results", "worker_unavailable"])
        self.assertFalse(health["healthy"])

    def test_cached_rows_return_ready_without_scheduling_refresh(self) -> None:
        original_read_cache = search_api._read_result_cache
        original_schedule = search_api._safe_schedule_backfill
        try:
            search_api._read_result_cache = lambda _key: {
                "status": "pending",
                "job_id": "job-1",
                "items": [{"note_id": "n1"}],
                "summary": {"note_count": 1},
                "pagination": {"total": 1, "page": 1, "size": 30, "has_more": False},
                "health": {"healthy": True, "reasons": []},
            }

            def _unexpected_schedule(*_args, **_kwargs):
                raise AssertionError("cached rows should not schedule refresh")

            search_api._safe_schedule_backfill = _unexpected_schedule
            response = search_api.search_brand_or_category(
                BrandCategorySearchRequest(query="YSL", mode="brand", page=1, size=30),
                db=object(),
            )
            self.assertEqual(response.data["status"], "ready")
            self.assertNotIn("pending_reason", response.data)
            self.assertNotIn("next_poll_after_ms", response.data)
            self.assertIn("served_from_cache", response.data["health"]["reasons"])
        finally:
            search_api._read_result_cache = original_read_cache
            search_api._safe_schedule_backfill = original_schedule

    def test_healthy_db_hit_does_not_schedule_background_backfill(self) -> None:
        original_read_cache = search_api._read_result_cache
        original_write_cache = search_api._write_result_cache
        original_query_v2 = search_api.query_brand_category_db_first_v2
        original_query_legacy = search_api.query_brand_category_db_first
        original_schedule = search_api._safe_schedule_backfill
        original_quota = search_api._has_recent_quota_exhausted_collect_task
        original_statement_timeout = search_api._run_with_statement_timeout
        try:
            search_api._read_result_cache = lambda _key: None
            search_api._write_result_cache = lambda *_args, **_kwargs: None
            search_api._has_recent_quota_exhausted_collect_task = lambda _db: False
            search_api._run_with_statement_timeout = lambda _db, _timeout_ms, fn: fn()
            search_api.query_brand_category_db_first = lambda *_args, **_kwargs: {
                "hit": False,
                "items": [],
                "summary": {},
                "pagination": {"total": 0},
                "freshness": None,
            }
            search_api.query_brand_category_db_first_v2 = lambda *_args, **_kwargs: {
                "hit": True,
                "items": [{"note_id": f"n{i}"} for i in range(30)],
                "summary": {"note_count": 100, "creator_count": 20, "comment_total": 50},
                "pagination": {"total": 100, "page": 1, "size": 30, "has_more": True},
                "freshness": datetime.now(timezone.utc).isoformat(),
            }

            def _unexpected_schedule(*_args, **_kwargs):
                raise AssertionError("healthy DB hit should not schedule background backfill")

            search_api._safe_schedule_backfill = _unexpected_schedule
            response = search_api.search_brand_or_category(
                BrandCategorySearchRequest(query="YSL", mode="brand", page=1, size=30),
                db=object(),
            )
            self.assertEqual(response.data["status"], "ready")
            self.assertEqual(response.data["pagination"]["total"], 100)
        finally:
            search_api._read_result_cache = original_read_cache
            search_api._write_result_cache = original_write_cache
            search_api.query_brand_category_db_first_v2 = original_query_v2
            search_api.query_brand_category_db_first = original_query_legacy
            search_api._safe_schedule_backfill = original_schedule
            search_api._has_recent_quota_exhausted_collect_task = original_quota
            search_api._run_with_statement_timeout = original_statement_timeout


if __name__ == "__main__":
    unittest.main()
