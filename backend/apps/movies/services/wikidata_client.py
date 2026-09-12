from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

from apps.movies.exceptions import (
    WikidataError,
    WikidataNotFoundError,
    WikidataUnavailableError,
)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

TMDB_MOVIE_ID_PROPERTY = "P4947"

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 8.0

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0

WIKIDATA_PACING_TIMESTAMP_KEY = "wikidata:pacing:last_request_at"
WIKIDATA_PACING_LOCK_KEY = "wikidata:pacing:lock"
PACING_LOCK_TIMEOUT_SECONDS = 2.0
PACING_LOCK_POLL_SECONDS = 0.02


@dataclass(slots=True)
class WikidataClient:
    session: requests.Session = field(default_factory=requests.Session)
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
    use_shared_pacing: bool = True
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
        self.session.headers["Accept"] = "application/sparql-results+json"
        self.min_request_interval = getattr(
            settings, "WIKIDATA_MIN_REQUEST_INTERVAL_SECONDS", self.min_request_interval
        )
        self.use_shared_pacing = getattr(
            settings, "WIKIDATA_USE_SHARED_PACING", self.use_shared_pacing
        )

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

    def _sparql(self, query: str) -> dict:
        return self._get(WIKIDATA_SPARQL_URL, params={"query": query, "format": "json"})

    def _get(self, url: str, params: Optional[dict] = None) -> dict:
        attempt = 0
        while True:
            attempt += 1
            self._wait_for_pacing()
            self._last_request_at = time.monotonic()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
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
                if attempt > self.max_retries:
                    raise WikidataUnavailableError(
                        f"Wikidata rate-limited '{url}' after {attempt} attempt(s)."
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

    def _wait_for_pacing(self) -> None:
        if self.min_request_interval <= 0:
            return
        if self.use_shared_pacing:
            self._wait_for_pacing_shared()
        else:
            self._wait_for_pacing_local()

    def _wait_for_pacing_local(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _wait_for_pacing_shared(self) -> None:
        while not cache.add(
            WIKIDATA_PACING_LOCK_KEY, "1", timeout=PACING_LOCK_TIMEOUT_SECONDS
        ):
            time.sleep(PACING_LOCK_POLL_SECONDS)

        try:
            last = cache.get(WIKIDATA_PACING_TIMESTAMP_KEY)
            now = time.time()
            if last is not None:
                remaining = self.min_request_interval - (now - last)
                if remaining > 0:
                    time.sleep(remaining)
                    now = time.time()
            cache.set(WIKIDATA_PACING_TIMESTAMP_KEY, now, timeout=60)
        finally:
            cache.delete(WIKIDATA_PACING_LOCK_KEY)

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
