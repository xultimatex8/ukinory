from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from django.conf import settings

from apps.movies.exceptions import (
    WikidataError,
    WikidataNotFoundError,
    WikidataUnavailableError,
)
from apps.movies.services.redis_pacing import wait_for_pacing

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

TMDB_MOVIE_ID_PROPERTY = "P4947"

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 8.0
MAX_RETRY_AFTER_SECONDS = 120.0

MAX_ENTITIES_PER_REQUEST = 50

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.25

WIKIDATA_PACING_KEY = "wikidata:pacing:next_slot"

SPARQL_ACCEPT = "application/sparql-results+json"
JSON_ACCEPT = "application/json"


@dataclass(slots=True)
class WikidataClient:
    session: requests.Session = field(default_factory=requests.Session)
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
    _last_request_at: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        user_agent = getattr(settings, "WIKIDATA_USER_AGENT", None)
        if not user_agent:
            raise WikidataError(
                "WIKIDATA_USER_AGENT is not configured. Set it in Django "
                "settings before using WikidataClient (required by "
                "Wikimedia's user-agent policy)."
            )
        self.session.headers["User-Agent"] = user_agent

    def find_qid_by_tmdb_id(self, tmdb_id: int) -> Optional[str]:
        query = f"""
        SELECT ?item WHERE {{
          ?item wdt:{TMDB_MOVIE_ID_PROPERTY} "{tmdb_id}".
        }}
        LIMIT 1
        """
        payload = self._sparql(query)
        bindings = payload.get("results", {}).get("bindings") or []
        if not bindings:
            return None
        uri = bindings[0]["item"]["value"]
        return uri.rsplit("/", 1)[-1]

    def sparql(self, query: str) -> dict:
        return self._sparql(query)

    def get_entities(
        self,
        qids: list[str],
        props: str,
        languages: tuple[str, ...] = ("en", "es"),
    ) -> dict[str, dict]:
        entities: dict[str, dict] = {}

        for start in range(0, len(qids), MAX_ENTITIES_PER_REQUEST):
            chunk = qids[start : start + MAX_ENTITIES_PER_REQUEST]
            payload = self._get(
                WIKIDATA_API_URL,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": props,
                    "languages": "|".join(languages),
                    "format": "json",
                },
                accept=JSON_ACCEPT,
            )

            if "error" in payload:
                raise WikidataError(f"Wikidata API error: {payload['error']}")

            for qid, entity in (payload.get("entities") or {}).items():
                if "missing" in entity:
                    continue
                entities[qid] = entity

        return entities

    def _sparql(self, query: str) -> dict:
        return self._get(
            WIKIDATA_SPARQL_URL,
            params={"query": query, "format": "json"},
            accept=SPARQL_ACCEPT,
        )

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        accept: str = JSON_ACCEPT,
    ) -> dict:
        attempt = 0
        while True:
            attempt += 1
            wait_for_pacing(WIKIDATA_PACING_KEY, self.min_request_interval)
            self._last_request_at = time.monotonic()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers={"Accept": accept},
                    timeout=self.timeout,
                )
            except requests.Timeout as exc:
                raise WikidataUnavailableError(
                    f"Wikidata timed out on '{url}': {exc}"
                ) from exc
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise WikidataUnavailableError(
                        f"Wikidata request to '{url}' failed after {attempt} "
                        f"attempt(s): {exc}"
                    ) from exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 404:
                raise WikidataNotFoundError(f"Wikidata has no resource at '{url}'.")

            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                if attempt > self.max_retries or retry_after > MAX_RETRY_AFTER_SECONDS:
                    raise WikidataUnavailableError(
                        f"Wikidata rate-limited '{url}' "
                        f"(Retry-After={retry_after}s, attempt {attempt})."
                    )
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                if attempt > self.max_retries:
                    raise WikidataUnavailableError(
                        f"Wikidata returned {response.status_code} for '{url}' "
                        f"after {attempt} attempt(s)."
                    )
                self._sleep_backoff(attempt)
                continue

            if not response.ok:
                raise WikidataError(
                    f"Wikidata request to '{url}' failed with "
                    f"{response.status_code}: {response.text[:200]}"
                )

            return response.json()

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float:
        header = response.headers.get("Retry-After")
        if header is None:
            return DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
        try:
            return max(float(header), 0.0)
        except ValueError:
            return DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2 ** (attempt - 1) * 0.5, MAX_BACKOFF_SECONDS))
