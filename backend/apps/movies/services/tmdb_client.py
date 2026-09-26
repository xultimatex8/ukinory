from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import requests
from django.conf import settings

from apps.movies.exceptions import (
    TMDbError,
    TMDbNotFoundError,
    TMDbRateLimitedError,
    TMDbUnavailableError,
)
from apps.movies.services.redis_pacing import wait_for_pacing

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_AFTER_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.05

TMDB_PACING_KEY = "tmdb:pacing:next_slot"


@dataclass(slots=True)
class TMDbClient:
    api_key: Optional[str] = None
    session: requests.Session = field(default_factory=requests.Session)
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
    _last_request_at: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or getattr(settings, "TMDB_API_KEY", None)
        if not self.api_key:
            raise TMDbError(
                "TMDB_API_KEY is not configured. Set it in Django settings "
                "(loaded from the environment) before using TMDbClient."
            )

    def get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> dict:
        url = f"{TMDB_BASE_URL}{path}"
        query = dict(params or {})
        query.setdefault("api_key", self.api_key)

        attempt = 0
        while True:
            attempt += 1
            wait_for_pacing(TMDB_PACING_KEY, self.min_request_interval)
            self._last_request_at = time.monotonic()
            try:
                response = self.session.get(url, params=query, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise TMDbUnavailableError(
                        f"TMDb request to '{path}' failed after {attempt} "
                        f"attempt(s): {exc}"
                    ) from exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 404:
                raise TMDbNotFoundError(f"TMDb has no resource at '{path}'.")

            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                if attempt > self.max_retries:
                    raise TMDbRateLimitedError(retry_after)
                logger.info(
                    "TMDb rate-limited request to '%s' (attempt %d/%d); "
                    "sleeping %.1fs before retrying.",
                    path, attempt, self.max_retries, retry_after,
                )
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                if attempt > self.max_retries:
                    raise TMDbUnavailableError(
                        f"TMDb returned {response.status_code} for '{path}' "
                        f"after {attempt} attempt(s)."
                    )
                self._sleep_backoff(attempt)
                continue

            if not response.ok:
                raise TMDbError(
                    f"TMDb request to '{path}' failed with "
                    f"{response.status_code}: {response.text[:200]}"
                )

            return response.json()

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float:
        header = response.headers.get("Retry-After")
        if header is None:
            return DEFAULT_RETRY_AFTER_SECONDS
        try:
            return max(float(header), 0.0)
        except ValueError:
            return DEFAULT_RETRY_AFTER_SECONDS

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2 ** (attempt - 1) * 0.5, MAX_BACKOFF_SECONDS))
