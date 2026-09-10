from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import requests
from django.conf import settings
from django.core.cache import cache

from apps.movies.exceptions import (
    TMDbError,
    TMDbNotFoundError,
    TMDbRateLimitedError,
    TMDbUnavailableError,
)

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_AFTER_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.25

TMDB_PACING_TIMESTAMP_KEY = "tmdb:pacing:last_request_at"
TMDB_PACING_LOCK_KEY = "tmdb:pacing:lock"
PACING_LOCK_TIMEOUT_SECONDS = 2.0
PACING_LOCK_POLL_SECONDS = 0.02


@dataclass(slots=True)
class TMDbClient:
    api_key: Optional[str] = None
    session: requests.Session = field(default_factory=requests.Session)
    max_retries: int = DEFAULT_MAX_RETRIES
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
    use_shared_pacing: bool = True
    _last_request_at: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or getattr(settings, "TMDB_API_KEY", None)
        if not self.api_key:
            raise TMDbError(
                "TMDB_API_KEY is not configured. Set it in Django settings "
                "(loaded from the environment) before using TMDbClient."
            )
        self.min_request_interval = getattr(
            settings, "TMDB_MIN_REQUEST_INTERVAL_SECONDS", self.min_request_interval
        )
        self.use_shared_pacing = getattr(
            settings, "TMDB_USE_SHARED_PACING", self.use_shared_pacing
        )

    def get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> dict:
        url = f"{TMDB_BASE_URL}{path}"
        query = dict(params or {})
        query.setdefault("api_key", self.api_key)

        attempt = 0
        while True:
            attempt += 1
            self._wait_for_pacing()
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
            TMDB_PACING_LOCK_KEY, "1", timeout=PACING_LOCK_TIMEOUT_SECONDS
        ):
            time.sleep(PACING_LOCK_POLL_SECONDS)

        try:
            last = cache.get(TMDB_PACING_TIMESTAMP_KEY)
            now = time.time()
            if last is not None:
                remaining = self.min_request_interval - (now - last)
                if remaining > 0:
                    time.sleep(remaining)
                    now = time.time()
            cache.set(TMDB_PACING_TIMESTAMP_KEY, now, timeout=60)
        finally:
            cache.delete(TMDB_PACING_LOCK_KEY)

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
