from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.movies.exceptions import (
    TMDbError,
    TMDbNotFoundError,
    TMDbRateLimitedError,
    TMDbUnavailableError,
)
from apps.movies.services.tmdb_client import (
    TMDB_PACING_KEY,
    TMDbClient,
)


@dataclass
class FakeResponse:
    status_code: int
    _json: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> dict[str, Any]:
        return self._json


@pytest.fixture(autouse=True)
def tmdb_api_key(settings):
    settings.TMDB_API_KEY = "test-key"


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def make_client(**overrides) -> TMDbClient:
    client = TMDbClient(**overrides)
    client.session = MagicMock(spec=requests.Session)
    return client


class TestConfiguration:
    def test_missing_api_key_raises(self, settings):
        settings.TMDB_API_KEY = None

        with pytest.raises(TMDbError, match="TMDB_API_KEY is not configured"):
            TMDbClient(api_key=None)

    def test_explicit_api_key_overrides_settings(self, settings):
        settings.TMDB_API_KEY = "from-settings"

        client = TMDbClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"

    def test_reads_min_request_interval_from_settings(self, settings):
        client = TMDbClient()

        assert client.min_request_interval == 0.075


class TestGetHappyPath:
    def test_returns_parsed_json(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, {"results": []})

        payload = client.get("/search/movie", params={"query": "Dune"})

        assert payload == {"results": []}

    def test_sends_api_key_as_query_param(self):
        client = make_client(api_key="my-key")
        client.session.get.return_value = FakeResponse(200, {})

        client.get("/movie/123")

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["api_key"] == "my-key"

    def test_does_not_overwrite_explicit_params(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, {})

        client.get("/search/movie", params={"query": "Dune", "year": 2021})

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["query"] == "Dune"
        assert kwargs["params"]["year"] == 2021


class TestGetErrorMapping:
    def test_404_raises_not_found(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(404)

        with pytest.raises(TMDbNotFoundError):
            client.get("/movie/999999")

    def test_other_4xx_raises_generic_tmdb_error(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(401, text="Invalid API key")

        with pytest.raises(TMDbError):
            client.get("/movie/1")

    def test_request_exception_retries_then_raises_unavailable(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(TMDbUnavailableError):
            client.get("/movie/1")

        assert client.session.get.call_count == 3

    def test_request_exception_recovers_on_retry(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = [
            requests.ConnectionError("boom"),
            FakeResponse(200, {"ok": True}),
        ]

        payload = client.get("/movie/1")

        assert payload == {"ok": True}


class TestRateLimiting:
    def test_429_retries_and_then_succeeds(self):
        client = make_client(max_retries=3)
        client.session.get.side_effect = [
            FakeResponse(429, headers={"Retry-After": "2"}),
            FakeResponse(200, {"results": []}),
        ]

        payload = client.get("/search/movie")

        assert payload == {"results": []}
        assert client.session.get.call_count == 2

    def test_429_exhausted_raises_rate_limited_with_retry_after(self):
        client = make_client(max_retries=1)
        client.session.get.return_value = FakeResponse(
            429, headers={"Retry-After": "5"}
        )

        with pytest.raises(TMDbRateLimitedError) as exc_info:
            client.get("/search/movie")

        assert exc_info.value.retry_after == 5.0

    def test_429_without_retry_after_header_uses_default(self):
        client = make_client(max_retries=0)
        client.session.get.return_value = FakeResponse(429, headers={})

        with pytest.raises(TMDbRateLimitedError) as exc_info:
            client.get("/search/movie")

        assert exc_info.value.retry_after == 1.0

    def test_429_with_malformed_retry_after_uses_default(self):
        client = make_client(max_retries=0)
        client.session.get.return_value = FakeResponse(
            429, headers={"Retry-After": "not-a-number"}
        )

        with pytest.raises(TMDbRateLimitedError) as exc_info:
            client.get("/search/movie")

        assert exc_info.value.retry_after == 1.0


class TestServerErrors:
    def test_5xx_retries_then_raises_unavailable(self):
        client = make_client(max_retries=2)
        client.session.get.return_value = FakeResponse(503)

        with pytest.raises(TMDbUnavailableError):
            client.get("/movie/1")

        assert client.session.get.call_count == 3

    def test_5xx_recovers_on_retry(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = [
            FakeResponse(500),
            FakeResponse(200, {"ok": True}),
        ]

        payload = client.get("/movie/1")

        assert payload == {"ok": True}


@pytest.mark.django_db
class TestSharedPacing:
    @patch("apps.movies.services.tmdb_client.wait_for_pacing")
    def test_stamps_timestamp_in_cache(self, mock_wait_for_pacing):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, {})

        client.get("/movie/1")

        mock_wait_for_pacing.assert_called_once_with(
            TMDB_PACING_KEY,
            client.min_request_interval,
        )

    @patch("apps.movies.services.tmdb_client.wait_for_pacing")
    def test_second_call_sleeps_out_the_remaining_interval(
        self, mock_wait_for_pacing
    ):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, {})

        client.get("/movie/1")
        client.get("/movie/2")

        assert mock_wait_for_pacing.call_count == 2
        assert mock_wait_for_pacing.call_args_list[0].args == (
            TMDB_PACING_KEY,
            client.min_request_interval,
        )
        assert mock_wait_for_pacing.call_args_list[1].args == (
            TMDB_PACING_KEY,
            client.min_request_interval,
        )

    @patch("apps.movies.services.tmdb_client.wait_for_pacing")
    def test_pacing_is_called_even_if_request_raises(self, mock_wait_for_pacing):
        client = make_client(max_retries=0)
        client.session.get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(TMDbUnavailableError):
            client.get("/movie/1")

        mock_wait_for_pacing.assert_called_once_with(
            TMDB_PACING_KEY,
            client.min_request_interval,
        )