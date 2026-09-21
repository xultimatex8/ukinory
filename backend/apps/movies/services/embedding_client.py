from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from google import genai
from google.genai.errors import APIError

from apps.common import api_quota
from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError
from apps.movies.dtos.batch_result import BatchResult

logger = logging.getLogger(__name__)

QUOTA_SYNC = "embedding_sync"
QUOTA_BATCH = "embedding_batch"

DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 16.0

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.5

EMBEDDING_PACING_TIMESTAMP_KEY = "embedding:pacing:last_request_at"
EMBEDDING_PACING_LOCK_KEY = "embedding:pacing:lock"
PACING_LOCK_TIMEOUT_SECONDS = 2.0
PACING_LOCK_POLL_SECONDS = 0.02

DIMENSIONS = 768

DEFAULT_SYNC_CHUNK_SIZE = 50

BATCH_RESULT_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_PARTIALLY_SUCCEEDED"}
BATCH_DONE_STATES = BATCH_RESULT_STATES | {
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


def _fit_dimensions(values: list[float]) -> list[float]:
    if len(values) < DIMENSIONS:
        raise EmbeddingError(
            f"Expected {DIMENSIONS} embedding dimensions, got {len(values)}."
        )
    values = list(values[:DIMENSIONS])
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values] if norm else values


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
        return self._embed_request([text])[0]

    def embed_many(
        self, texts: list[str], chunk_size: int = DEFAULT_SYNC_CHUNK_SIZE
    ) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), chunk_size):
            results.extend(self._embed_request(texts[i : i + chunk_size]))
            
        return results

    def _embed_request(self, contents: list[str]) -> list[list[float]]:
        if not contents:
            return []

        attempt = 0
        while True:
            attempt += 1
            self._consume_quota(
                QUOTA_SYNC,
                sum(api_quota.text_cost(QUOTA_SYNC, t) for t in contents),
            )
            self._wait_for_pacing()
            self._last_request_at = time.monotonic()
            try:
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config={"output_dimensionality": DIMENSIONS},
                )
                embeddings = response.embeddings or []
                if len(embeddings) != len(contents):
                    raise EmbeddingError(
                        f"Expected {len(contents)} embeddings, got {len(embeddings)}."
                    )
                return [_fit_dimensions(e.values) for e in embeddings]
            except APIError as exc:
                status = getattr(exc, "code", None)
                if attempt > self.max_retries:
                    kind = "rate-limited" if status == 429 else "failed"
                    raise EmbeddingUnavailableError(
                        f"Embedding API {kind} after {attempt} attempt(s): {exc}"
                    ) from exc
                if status == 429:
                    logger.info(
                        "Embedding API rate-limited (attempt %d/%d); backing off.",
                        attempt, self.max_retries,
                    )
                self._sleep_backoff(attempt)

    def create_batch(self, texts: list[str], display_name: str, cost: int | None = None) -> str:
        if not texts:
            raise EmbeddingError("Cannot create an empty embedding batch.")
        if cost is None:
            cost = sum(api_quota.text_cost(QUOTA_BATCH, t) for t in texts)
        self._consume_quota(QUOTA_BATCH, cost)
        try:
            job = self._client.batches.create_embeddings(
                model=self.model,
                src={
                    "inlined_requests": {
                        "contents": texts,
                        "config": {"output_dimensionality": DIMENSIONS},
                    }
                },
                config={"display_name": display_name},
            )
        except APIError as exc:
            api_quota.refund(QUOTA_BATCH, cost)
            raise EmbeddingUnavailableError(f"Could not create embedding batch: {exc}") from exc
        
        return job.name

    def get_batch(self, name: str) -> BatchResult:
        try:
            job = self._client.batches.get(name=name)
        except APIError as exc:
            raise EmbeddingUnavailableError(f"Could not fetch batch '{name}': {exc}") from exc

        state = job.state.name if job.state else "UNKNOWN"
        if state not in BATCH_RESULT_STATES:
            error = str(job.error) if getattr(job, "error", None) else None
            return BatchResult(state=state, error=error)

        embeddings: list[Optional[list[float]]] = []
        item_errors: list[Optional[str]] = []

        for item in job.dest.inlined_embed_content_responses or []:
            item_error = getattr(item, "error", None)

            if item_error or not getattr(item, "response", None):
                embeddings.append(None)
                item_errors.append(str(item_error) if item_error else "Missing embedding response.")
                continue

            embeddings.append(_fit_dimensions(item.response.embedding.values))
            item_errors.append(None)

        return BatchResult(state=state, embeddings=embeddings, item_errors=item_errors)

    @staticmethod
    def _consume_quota(client_name: str, units: int) -> None:
        try:
            api_quota.consume(client_name, units)
        except api_quota.QuotaExceeded as exc:
            raise EmbeddingUnavailableError(str(exc)) from exc

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
