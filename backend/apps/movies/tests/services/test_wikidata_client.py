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
    MAX_ENTITIES_PER_REQUEST,
    WIKIDATA_API_URL,
    WIKIDATA_PACING_KEY,
    WIKIDATA_SPARQL_URL,
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


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def make_client(**overrides) -> WikidataClient:
    client = WikidataClient(**overrides)
    client.session = MagicMock(spec=requests.Session)
    return client


def bindings_payload(*items: dict) -> dict:
    return {"results": {"bindings": list(items)}}


def entities_payload(*qids: str, missing: tuple[str, ...] = ()) -> dict:
    entities = {qid: {"id": qid, "type": "item"} for qid in qids}
    entities.update({qid: {"id": qid, "missing": ""} for qid in missing})
    return {"entities": entities}


class TestConfiguration:
    def test_missing_user_agent_raises(self, settings):
        settings.WIKIDATA_USER_AGENT = None

        with pytest.raises(
            WikidataError,
            match="WIKIDATA_USER_AGENT is not configured",
        ):
            WikidataClient()

    def test_sets_user_agent_header_from_settings(self, settings):
        settings.WIKIDATA_USER_AGENT = "my-agent/2.0"

        client = WikidataClient()

        assert client.session.headers["User-Agent"] == "my-agent/2.0"

    def test_reads_min_request_interval_from_settings(self, settings):
        client = WikidataClient()

        assert client.min_request_interval == 0.25


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

        args, kwargs = client.session.get.call_args
        assert args[0] == WIKIDATA_SPARQL_URL
        assert kwargs["params"]["query"] == "SELECT ?item WHERE { }"
        assert kwargs["params"]["format"] == "json"

    def test_sends_sparql_accept_header_per_request(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(200, bindings_payload())

        client.sparql("SELECT ?item WHERE { }")

        _, kwargs = client.session.get.call_args
        assert kwargs["headers"]["Accept"] == "application/sparql-results+json"


class TestGetEntities:
    def test_returns_entities_keyed_by_qid(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200, entities_payload("Q1", "Q2")
        )

        entities = client.get_entities(["Q1", "Q2"], props="labels")

        assert set(entities) == {"Q1", "Q2"}
        assert entities["Q1"]["id"] == "Q1"

    def test_sends_wbgetentities_params(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200, entities_payload("Q1", "Q2")
        )

        client.get_entities(["Q1", "Q2"], props="claims|labels")

        args, kwargs = client.session.get.call_args
        assert args[0] == WIKIDATA_API_URL
        assert kwargs["params"] == {
            "action": "wbgetentities",
            "ids": "Q1|Q2",
            "props": "claims|labels",
            "languages": "en|es",
            "format": "json",
        }

    def test_uses_json_accept_header(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200, entities_payload("Q1")
        )

        client.get_entities(["Q1"], props="labels")

        _, kwargs = client.session.get.call_args
        assert kwargs["headers"]["Accept"] == "application/json"

    def test_custom_languages_are_joined(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200, entities_payload("Q1")
        )

        client.get_entities(["Q1"], props="labels", languages=("fr", "de"))

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["languages"] == "fr|de"

    def test_missing_entities_are_skipped(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200, entities_payload("Q1", missing=("Q999",))
        )

        entities = client.get_entities(["Q1", "Q999"], props="labels")

        assert set(entities) == {"Q1"}

    def test_splits_requests_at_the_api_limit(self):
        client = make_client()

        def respond(url, params=None, **kwargs):
            return FakeResponse(
                200,
                entities_payload(*params["ids"].split("|")),
            )

        client.session.get.side_effect = respond
        qids = [f"Q{i}" for i in range(1, 121)]

        entities = client.get_entities(qids, props="labels")

        sizes = [
            len(call.kwargs["params"]["ids"].split("|"))
            for call in client.session.get.call_args_list
        ]
        assert sizes == [MAX_ENTITIES_PER_REQUEST, MAX_ENTITIES_PER_REQUEST, 20]
        assert len(entities) == 120

    def test_empty_list_makes_no_request(self):
        client = make_client()

        assert client.get_entities([], props="labels") == {}
        client.session.get.assert_not_called()

    def test_api_error_payload_raises(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            200,
            {"error": {"code": "no-such-entity", "info": "nope"}},
        )

        with pytest.raises(WikidataError, match="Wikidata API error"):
            client.get_entities(["Q1"], props="labels")


class TestErrorMapping:
    def test_404_raises_not_found(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(404)

        with pytest.raises(WikidataNotFoundError):
            client.sparql("SELECT ?item WHERE { }")

    def test_other_4xx_raises_generic_wikidata_error(self):
        client = make_client()
        client.session.get.return_value = FakeResponse(
            400,
            text="Malformed query",
        )

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


class TestTimeouts:
    def test_timeout_is_not_retried(self):
        client = make_client(max_retries=3)
        client.session.get.side_effect = requests.ReadTimeout("slow")

        with pytest.raises(WikidataUnavailableError, match="timed out"):
            client.sparql("SELECT ?item WHERE { }")

        assert client.session.get.call_count == 1

    def test_timeout_on_the_api_is_not_retried_either(self):
        client = make_client(max_retries=3)
        client.session.get.side_effect = requests.ReadTimeout("slow")

        with pytest.raises(WikidataUnavailableError):
            client.get_entities(["Q1"], props="labels")

        assert client.session.get.call_count == 1


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
            429,
            headers={"Retry-After": "5"},
        )

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")

        assert client.session.get.call_count == 2

    def test_429_with_a_very_long_retry_after_aborts_immediately(self):
        client = make_client(max_retries=3)
        client.session.get.return_value = FakeResponse(
            429,
            headers={"Retry-After": "3600"},
        )

        with pytest.raises(WikidataUnavailableError, match="Retry-After"):
            client.sparql("SELECT ?item WHERE { }")

        assert client.session.get.call_count == 1

    def test_429_sleeps_for_the_advertised_retry_after(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)
        client = make_client(max_retries=3)
        client.session.get.side_effect = [
            FakeResponse(429, headers={"Retry-After": "7"}),
            FakeResponse(200, bindings_payload()),
        ]

        client.sparql("SELECT ?item WHERE { }")

        assert 7.0 in sleeps


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


@pytest.mark.django_db
class TestSharedPacing:
    def test_stamps_timestamp_in_cache(self, monkeypatch):
        from apps.movies.services import wikidata_client

        calls: list[tuple[str, float]] = []

        def fake_wait_for_pacing(key: str, min_interval: float) -> None:
            calls.append((key, min_interval))

        monkeypatch.setattr(
            wikidata_client,
            "wait_for_pacing",
            fake_wait_for_pacing,
        )

        client = make_client()
        client.session.get.return_value = FakeResponse(
            200,
            bindings_payload(),
        )

        client.sparql("SELECT ?item WHERE { }")

        assert calls == [
            (WIKIDATA_PACING_KEY, client.min_request_interval),
        ]

    def test_second_call_sleeps_out_the_remaining_interval(
        self,
        monkeypatch,
    ):
        from apps.movies.services import wikidata_client

        calls: list[tuple[str, float]] = []

        def fake_wait_for_pacing(key: str, min_interval: float) -> None:
            calls.append((key, min_interval))

        monkeypatch.setattr(
            wikidata_client,
            "wait_for_pacing",
            fake_wait_for_pacing,
        )

        client = make_client()
        client.session.get.return_value = FakeResponse(
            200,
            bindings_payload(),
        )

        client.sparql("SELECT ?item WHERE { }")
        client.sparql("SELECT ?item WHERE { }")

        assert calls == [
            (WIKIDATA_PACING_KEY, client.min_request_interval),
            (WIKIDATA_PACING_KEY, client.min_request_interval),
        ]

    def test_api_calls_share_the_same_pacing_as_sparql(
        self,
        monkeypatch,
    ):
        from apps.movies.services import wikidata_client

        calls: list[tuple[str, float]] = []

        def fake_wait_for_pacing(key: str, min_interval: float) -> None:
            calls.append((key, min_interval))

        monkeypatch.setattr(
            wikidata_client,
            "wait_for_pacing",
            fake_wait_for_pacing,
        )

        client = make_client()
        client.session.get.side_effect = [
            FakeResponse(200, bindings_payload()),
            FakeResponse(200, entities_payload("Q1")),
        ]

        client.sparql("SELECT ?item WHERE { }")
        client.get_entities(["Q1"], props="labels")

        assert calls == [
            (WIKIDATA_PACING_KEY, client.min_request_interval),
            (WIKIDATA_PACING_KEY, client.min_request_interval),
        ]

    def test_pacing_is_applied_even_if_request_raises(
        self,
        monkeypatch,
    ):
        from apps.movies.services import wikidata_client

        calls: list[tuple[str, float]] = []

        def fake_wait_for_pacing(key: str, min_interval: float) -> None:
            calls.append((key, min_interval))

        monkeypatch.setattr(
            wikidata_client,
            "wait_for_pacing",
            fake_wait_for_pacing,
        )

        client = make_client(max_retries=0)
        client.session.get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(WikidataUnavailableError):
            client.sparql("SELECT ?item WHERE { }")

        assert calls == [
            (WIKIDATA_PACING_KEY, client.min_request_interval),
        ]


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
