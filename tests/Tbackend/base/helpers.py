import unittest
from asyncio import get_event_loop_policy
from typing import Any, Dict, List
from unittest.mock import patch

from backend.base.definitions import Constants
from backend.base.helpers import AsyncSession, Session, get_ratelimit_wait


class ratelimit_wait(unittest.TestCase):
    def test_retry_after_in_seconds_is_honoured(self):
        self.assertEqual(get_ratelimit_wait({"Retry-After": "5"}, 1), 5.0)

    def test_retry_after_of_zero_is_honoured(self):
        self.assertEqual(get_ratelimit_wait({"Retry-After": "0"}, 3), 0.0)

    def test_retry_after_is_capped(self):
        self.assertEqual(
            get_ratelimit_wait({"Retry-After": "3600"}, 1),
            float(Constants.MAX_RATELIMIT_WAIT)
        )

    def test_retry_after_in_the_past_is_not_negative(self):
        self.assertEqual(
            get_ratelimit_wait(
                {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}, 1
            ),
            0.0
        )

    def test_unusable_retry_after_falls_back_to_backoff(self):
        self.assertEqual(
            get_ratelimit_wait({"Retry-After": "soon"}, 1),
            float(Constants.BACKOFF_FACTOR_RETRIES)
        )

    def test_missing_retry_after_backs_off_exponentially(self):
        self.assertEqual(
            [get_ratelimit_wait({}, round) for round in (1, 2, 3, 4)],
            [
                float(Constants.BACKOFF_FACTOR_RETRIES * 2 ** (round - 1))
                for round in (1, 2, 3, 4)
            ]
        )


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status
        self.headers: Dict[str, str] = {"Retry-After": "0"}
        self.url = "https://example.com"
        self.released = False

    async def text(self) -> str:
        return ""

    def release(self) -> None:
        self.released = True


class FakeRequest:
    method = "GET"
    url = "https://example.com"


class FakeSyncResponse:
    def __init__(self, status: int) -> None:
        self.status_code = status
        self.headers: Dict[str, str] = {"Retry-After": "0"}
        self.url = "https://example.com"
        self.request = FakeRequest()
        self.text = ""
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeFlareSolverr:
    def get_ua_cookies(self, url: str):
        return Constants.DEFAULT_USERAGENT, {}

    def handle_cf_block(self, url: str, headers):
        return None


class async_session_ratelimit_retries(unittest.TestCase):
    """A rate limited response has to be retried, and only handed back to the
    caller once the retries are exhausted. Otherwise a burst of requests to a
    single source makes every request but the first few fail permanently.
    """

    def run_session(self, statuses: List[int]) -> Any:
        self.responses = [FakeResponse(status) for status in statuses]
        responses = self.responses
        calls: List[Any] = []

        async def fake_request(self, *args, **kwargs):
            calls.append(args)
            return responses[len(calls) - 1]

        async def main():
            with patch(
                "backend.implementations.flaresolverr.FlareSolverr",
                FakeFlareSolverr
            ), patch(
                "aiohttp.ClientSession._request", fake_request
            ):
                async with AsyncSession() as session:
                    return await session._request(
                        "GET", "https://example.com"
                    ), len(calls)

        loop = get_event_loop_policy().new_event_loop()
        try:
            return loop.run_until_complete(main())
        finally:
            loop.close()

    def test_rate_limited_request_is_retried(self):
        response, calls = self.run_session([429, 429, 200])

        self.assertEqual(response.status, 200)
        self.assertEqual(calls, 3)

    def test_successful_request_is_not_retried(self):
        response, calls = self.run_session([200])

        self.assertEqual(response.status, 200)
        self.assertEqual(calls, 1)

    def test_exhausted_retries_return_the_rate_limited_response(self):
        response, calls = self.run_session(
            [429] * Constants.TOTAL_RETRIES
        )

        self.assertEqual(response.status, 429)
        self.assertEqual(calls, Constants.TOTAL_RETRIES)

    def test_abandoned_responses_are_released(self):
        self.run_session([429, 429, 200])

        self.assertEqual(
            [r.released for r in self.responses],
            [True, True, False]
        )


class session_ratelimit_retries(unittest.TestCase):
    """The same for the sync session, which is what fetches the web pages and
    starts the file downloads.
    """

    def run_session(self, statuses: List[int]) -> Any:
        self.responses = [FakeSyncResponse(status) for status in statuses]
        responses = self.responses
        calls: List[Any] = []

        def fake_request(self, *args, **kwargs):
            calls.append(args)
            return responses[len(calls) - 1]

        with patch(
            "backend.implementations.flaresolverr.FlareSolverr",
            FakeFlareSolverr
        ), patch(
            "requests.Session.request", fake_request
        ):
            session = Session()
            return session.request(
                "GET", "https://example.com", stream=True
            ), len(calls)

    def test_rate_limited_request_is_retried(self):
        response, calls = self.run_session([429, 429, 200])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, 3)

    def test_successful_request_is_not_retried(self):
        response, calls = self.run_session([200])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, 1)

    def test_exhausted_retries_return_the_rate_limited_response(self):
        response, calls = self.run_session(
            [429] * Constants.TOTAL_RETRIES
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(calls, Constants.TOTAL_RETRIES)

    def test_abandoned_responses_are_closed(self):
        self.run_session([429, 429, 200])

        self.assertEqual(
            [r.closed for r in self.responses],
            [True, True, False]
        )
