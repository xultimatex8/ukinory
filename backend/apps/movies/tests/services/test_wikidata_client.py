from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from apps.movies.exceptions import (
    WikidataError,
    WikidataNotFoundError,
    WikidataUnavailableError,
)
from apps.movies.services.wikidata_client import (
    WIKIDATA_PACING_TIMESTAMP_KEY,
    WikidataClient,
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
def wikidata_user_agent(settings):
    settings.WIKIDATA_USER_AGENT = "ukinory-test/1.0 (test@example.com)"
    settings.WIKIDATA_USE_SHARED_PACING = False
    settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 0.0


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Every retry/backoff path in WikidataClient sleeps; none of these
    tests should actually wait for it."""
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def make_client(**overrides) -> WikidataClient:
    client = WikidataClient(**overrides)
    client.session = MagicMock(spec=requests.Session)
    return client


def bindings_payload(*items: dict) -> dict:
    return {"results": {"bindings": list(items)}}


class TestConfiguration:
    def test_missing_user_agent_raises(self, settings):
        settings.WIKIDATA_USER_AGENT = None

        with pytest.raises(WikidataError, match="WIKIDATA_USER_AGENT is not configured"):
            WikidataClient()

    def test_sets_user_agent_header_from_settings(self, settings):
        settings.WIKIDATA_USER_AGENT = "my-agent/2.0"

        client = WikidataClient()

        assert client.session.headers["User-Agent"] == "my-agent/2.0"

    def test_sets_default_accept_header(self):
        client = WikidataClient()

        assert client.session.headers["Accept"] == "application/sparql-results+json"

    def test_reads_min_request_interval_from_settings(self, settings):
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 0.75

        client = WikidataClient()

        assert client.min_request_interval == 0.75

    def test_reads_use_shared_pacing_from_settings(self, settings):
        settings.WIKIDATA_USE_SHARED_PACING = True

        client = WikidataClient()

        assert client.use_shared_pacing is True


class TestSparqlHappyPath:
    def test_returns_parsed_json(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        payload = client.sparql("SELECT ?item WHERE { ?item wdt:P31 wd:Q11424. }")

        assert payload == bindings_payload()

    def test_sends_query_and_format_params(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        client.sparql("SELECT ?item WHERE { }")

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["query"] == "SELECT ?item WHERE { }"
        assert kwargs["params"]["format"] == "json"


class TestErrorMapping:
    def test_404_raises_not_found(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(404)

        with pytest.raises(WikidataNotFoundError):
            client.sparql("SELECT ?item WHERE { }")

    def test_other_4xx_raises_generic_wikidata_error(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(400, text="Malformed query")

        with pytest.raises(WikidataError):
            client.sparql("not a valid query")

    def test_request_exception_retries_then_raises_unavailable(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")

        assert client.session.get.call_count == 3

    def test_request_exception_recovers_on_retry(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = [
            requests.ConnectionError("boom"),
            FakeResponse(200, bindings_payload()),
        ]

        payload = client.sparql("SELECT ?item WHERE { }")

        assert payload == bindings_payload()


class TestRateLimiting:
    def test_429_retries_and_then_succeeds(self):
        client = make_client(max_retries=3)
        client.session.get.side_effect = [
            FakeResponse(429, headers={"Retry-After": "2"}),
            FakeResponse(200, bindings_payload()),
        ]

        payload = client.sparql("SELECT ?item WHERE { }")

        assert payload == bindings_payload()
        assert client.session.get.call_count == 2

    def test_429_exhausted_raises_unavailable(self):
        client = make_client(max_retries=1)
        client.session.get.return_value = FakeResponse(
            429, headers={"Retry-After": "5"}
        )

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")


class TestServerErrors:
    def test_5xx_retries_then_raises_unavailable(self):
        client = make_client(max_retries=2)
        client.session.get.return_value = FakeResponse(503)

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")

        assert client.session.get.call_count == 3

    def test_5xx_recovers_on_retry(self):
        client = make_client(max_retries=2)
        client.session.get.side_effect = [
            FakeResponse(500),
            FakeResponse(200, bindings_payload()),
        ]

        payload = client.sparql("SELECT ?item WHERE { }")

        assert payload == bindings_payload()


class TestLocalPacing:
    def test_no_sleep_on_first_call(self, settings, monkeypatch):
        settings.WIKIDATA_USE_SHARED_PACING = False
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 1.0
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client.sparql("SELECT ?item WHERE { }")

        assert sleeps == []

    def test_second_call_sleeps_out_the_remaining_interval(
        self, settings, monkeypatch
    ):
        settings.WIKIDATA_USE_SHARED_PACING = False
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 1.0
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        fake_clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

        client.sparql("SELECT ?item WHERE { }")
        fake_clock[0] = 100.3
        client.sparql("SELECT ?item WHERE { }")

        assert sleeps == [pytest.approx(0.7)]

    def test_no_sleep_when_min_interval_is_zero(self, settings, monkeypatch):
        settings.WIKIDATA_USE_SHARED_PACING = False
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 0.0
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client.sparql("SELECT ?item WHERE { }")
        client.sparql("SELECT ?item WHERE { }")

        assert sleeps == []


@pytest.mark.django_db
class TestSharedPacing:
    def test_stamps_timestamp_in_cache(self, settings):
        from django.core.cache import cache

        settings.WIKIDATA_USE_SHARED_PACING = True
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 1.0
        cache.clear()
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        client.sparql("SELECT ?item WHERE { }")

        assert cache.get(WIKIDATA_PACING_TIMESTAMP_KEY) is not None

    def test_second_call_sleeps_out_the_remaining_interval(
        self, settings, monkeypatch
    ):
        from django.core.cache import cache

        settings.WIKIDATA_USE_SHARED_PACING = True
        settings.WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS = 1.0
        cache.clear()
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        fake_clock = [1_000.0]
        monkeypatch.setattr(time, "time", lambda: fake_clock[0])
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client.sparql("SELECT ?item WHERE { }")
        fake_clock[0] = 1_000.4
        client.sparql("SELECT ?item WHERE { }")

        assert any(s == pytest.approx(0.6) for s in sleeps)

    def test_lock_is_released_even_if_request_raises(self, settings):
        from django.core.cache import cache
        from apps.movies.services.wikidata_client import WIKIDATA_PACING_LOCK_KEY

        settings.WIKIDATA_USE_SHARED_PACING = True
        cache.clear()
        client = make_client(max_retries=0)
        client.session.get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")

        assert cache.get(WIKIDATA_PACING_LOCK_KEY) is None


class TestFindQidByTmdbId:
    def test_returns_qid_from_binding(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200,
            bindings_payload(
                {"item": {"value": "http://www.wikidata.org/entity/Q15147339"}}
            ),
        )

        qid = client.find_qid_by_tmdb_id(438631)

        assert qid == "Q15147339"

    def test_returns_none_when_no_bindings(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        assert client.find_qid_by_tmdb_id(438631) is None

    def test_embeds_tmdb_id_in_the_query(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        client.find_qid_by_tmdb_id(438631)

        _, kwargs = client.session.get.call_args
        assert '"438631"' in kwargs["params"]["query"]
