import unittest

import requests

from app.services.huitun_client import HuitunClient
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

    def test_huitun_client_reuses_session(self) -> None:
        client = HuitunClient()
        self.assertIsInstance(client.session, requests.Session)

    def test_read_search_retries_transient_http_errors(self) -> None:
        class _Response:
            def __init__(self, status_code: int):
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError("temporary", response=self)

            def json(self):
                return {"status": 200, "data": []}

        class _Session:
            def __init__(self):
                self.calls = 0

            def get(self, *_args, **_kwargs):
                self.calls += 1
                return _Response(503 if self.calls == 1 else 200)

        client = HuitunClient()
        fake_session = _Session()
        client.session = fake_session  # type: ignore[assignment]
        result = client.search_notes(keyword="防晒")
        self.assertEqual(result["status"], 200)
        self.assertEqual(fake_session.calls, 2)

    def test_async_create_does_not_retry_to_avoid_duplicate_tasks(self) -> None:
        class _Response:
            status_code = 503

            def raise_for_status(self):
                raise requests.HTTPError("temporary", response=self)

        class _Session:
            def __init__(self):
                self.calls = 0

            def get(self, *_args, **_kwargs):
                self.calls += 1
                return _Response()

        client = HuitunClient()
        fake_session = _Session()
        client.session = fake_session  # type: ignore[assignment]
        with self.assertRaises(requests.HTTPError):
            client.create_note_info(note_link="note-1", back_url="https://example.com/back")
        self.assertEqual(fake_session.calls, 1)


if __name__ == "__main__":
    unittest.main()
