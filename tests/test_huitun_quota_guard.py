import unittest

from app.tasks import jobs


class HuitunQuotaGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        jobs._quota_cache = None

    def tearDown(self) -> None:
        jobs._quota_cache = None

    def test_note_info_quota_exhausted_when_remaining_zero(self) -> None:
        original_get_quota = jobs.client.get_quota
        try:
            jobs.client.get_quota = lambda: {"status": 200, "data": {"note_info": 0, "note_comment": 3}}  # type: ignore[method-assign]
            self.assertTrue(jobs._is_huitun_quota_exhausted("note_info"))
            self.assertFalse(jobs._is_huitun_quota_exhausted("note_comment"))
        finally:
            jobs.client.get_quota = original_get_quota  # type: ignore[method-assign]

    def test_quota_error_matches_provider_messages(self) -> None:
        self.assertTrue(jobs._is_quota_error(RuntimeError("剩余次数不足")))
        self.assertTrue(jobs._is_quota_error(RuntimeError("quota exhausted")))
        self.assertFalse(jobs._is_quota_error(RuntimeError("temporary timeout")))


if __name__ == "__main__":
    unittest.main()
