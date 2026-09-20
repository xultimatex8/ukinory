from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from google import genai
from google.genai.errors import APIError

from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 16.0

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.5

EMBEDDING_PACING_TIMESTAMP_KEY = "embedding:pacing:last_request_at"
EMBEDDING_PACING_LOCK_KEY = "embedding:pacing:lock"
PACING_LOCK_TIMEOUT_SECONDS = 2.0
PACING_LOCK_POLL_SECONDS = 0.02

DIMENSIONS = 768



@dataclass(slots=True)
class EmbeddingClient:
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    max_retries: int = DEFAULT_MAX_RETRIES
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
    _client: genai.Client = field(init=False, repr=False)
    _last_request_at: Optional[float] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or getattr(settings, "GEMINI_API_KEY", None)
        if not self.api_key:
            raise EmbeddingError(
                "GEMINI_API_KEY is not configured. Set it in Django settings "
                "(loaded from the environment) before using EmbeddingClient."
            )
        self.model = getattr(settings, "EMBEDDING_MODEL", self.model)
        self.min_request_interval = getattr(
            settings, "EMBEDDING_MIN_REQUEST_INTERVAL_SECONDS", self.min_request_interval
        )
        self._client = genai.Client(api_key=self.api_key)

    def embed(self, text: str) -> list[float]:
        attempt = 0
        while True:
            attempt += 1
            self._wait_for_pacing()
            self._last_request_at = time.monotonic()
            try:
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=text,
                    config={"output_dimensionality": DIMENSIONS},
                )

                values = response.embeddings[0].values

                if len(values) != DIMENSIONS:
                    raise EmbeddingError(
                        f"Expected {DIMENSIONS} embedding dimensions, "
                        f"got {len(values)}."
                    )

                return values
            except APIError as exc:
                status = getattr(exc, "code", None)
                if status == 429:
                    if attempt > self.max_retries:
                        raise EmbeddingUnavailableError(
                            f"Embedding API rate-limited after {attempt} attempt(s)."
                        ) from exc
                    logger.info(
                        "Embedding API rate-limited (attempt %d/%d); backing off.",
                        attempt, self.max_retries,
                    )
                    self._sleep_backoff(attempt)
                    continue
                if attempt > self.max_retries:
                    raise EmbeddingUnavailableError(
                        f"Embedding API failed after {attempt} attempt(s): {exc}"
                    ) from exc
                self._sleep_backoff(attempt)

    def _wait_for_pacing(self) -> None:
        if self.min_request_interval <= 0:
            return
        self._wait_for_pacing_shared()

    def _wait_for_pacing_shared(self) -> None:
        while not cache.add(
            EMBEDDING_PACING_LOCK_KEY, "1", timeout=PACING_LOCK_TIMEOUT_SECONDS
        ):
            time.sleep(PACING_LOCK_POLL_SECONDS)
        try:
            last = cache.get(EMBEDDING_PACING_TIMESTAMP_KEY)
            now = time.time()
            if last is not None:
                remaining = self.min_request_interval - (now - last)
                if remaining > 0:
                    time.sleep(remaining)
                    now = time.time()
            cache.set(EMBEDDING_PACING_TIMESTAMP_KEY, now, timeout=60)
        finally:
            cache.delete(EMBEDDING_PACING_LOCK_KEY)

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(min(2 ** (attempt - 1) * 0.5, MAX_BACKOFF_SECONDS))
