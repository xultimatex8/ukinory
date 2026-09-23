from __future__ import annotations

import math
import time
from unittest.mock import MagicMock

import pytest
from google.genai.errors import APIError

from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError
from apps.movies.services.embedding_client import (
    DIMENSIONS,
    EMBEDDING_PACING_LOCK_KEY,
    EMBEDDING_PACING_TIMESTAMP_KEY,
    EmbeddingClient,
)


class FakeAPIError(APIError):
    def __init__(self, code: int):
        self.code = code
        Exception.__init__(self, f"fake api error {code}")


@pytest.fixture(autouse=True)
def embedding_api_key(settings):
    settings.GEMINI_API_KEY = "test-key"


@pytest.fixture(autouse=True)
def mock_genai_client_class(monkeypatch):
    mock_client_cls = MagicMock()
    monkeypatch.setattr(
        "apps.movies.services.embedding_client.genai.Client", mock_client_cls
    )
    return mock_client_cls


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def make_client(**overrides) -> EmbeddingClient:
    return EmbeddingClient(**overrides)


def embed_response(values: list[float]):
    embedding = MagicMock()
    embedding.values = values

    response = MagicMock()
    response.embeddings = [embedding]

    return response


class TestConfiguration:
    def test_missing_api_key_raises(self, settings):
        settings.GEMINI_API_KEY = None

        with pytest.raises(EmbeddingError, match="GEMINI_API_KEY is not configured"):
            EmbeddingClient(api_key=None)

    def test_explicit_api_key_overrides_settings(self, settings):
        settings.GEMINI_API_KEY = "from-settings"

        client = EmbeddingClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"

    def test_uses_default_model(self):
        client = EmbeddingClient()

        assert client.model == "gemini-embedding-001"

    def test_uses_default_min_request_interval(self):
        client = EmbeddingClient()

        assert client.min_request_interval == 0.85


class TestEmbedHappyPath:
    def test_returns_normalized_embedding_values(self):
        client = make_client()
        values = [0.1] * DIMENSIONS

        client._client.models.embed_content.return_value = embed_response(values)

        result = client.embed("some movie text")

        expected_value = 1 / math.sqrt(DIMENSIONS)
        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )

    def test_sends_configured_model_text(self):
        client = make_client(model="custom-model")
        client._client.models.embed_content.return_value = embed_response(
            [0.0] * DIMENSIONS
        )

        client.embed("some movie text")

        _, kwargs = client._client.models.embed_content.call_args

        assert kwargs["model"] == "custom-model"
        assert kwargs["contents"] == ["some movie text"]
        assert kwargs["config"] == {"output_dimensionality": DIMENSIONS}


class TestEmbedValidation:
    def test_dimension_mismatch_raises_embedding_error(self):
        client = make_client()

        client._client.models.embed_content.return_value = embed_response(
            [0.1, 0.2, 0.3]
        )

        with pytest.raises(EmbeddingError):
            client.embed("some movie text")


class TestRateLimiting:
    def test_429_retries_and_then_succeeds(self):
        client = make_client(max_retries=2)
        values = [1.0] * DIMENSIONS

        client._client.models.embed_content.side_effect = [
            FakeAPIError(429),
            embed_response(values),
        ]

        result = client.embed("text")

        expected_value = 1 / math.sqrt(DIMENSIONS)

        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )
        assert client._client.models.embed_content.call_count == 2

    def test_429_exhausted_raises_unavailable(self):
        client = make_client(max_retries=1)
        client._client.models.embed_content.side_effect = FakeAPIError(429)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        assert client._client.models.embed_content.call_count == 2


class TestServerErrors:
    def test_5xx_retries_and_then_succeeds(self):
        client = make_client(max_retries=2)
        values = [1.0] * DIMENSIONS

        client._client.models.embed_content.side_effect = [
            FakeAPIError(500),
            embed_response(values),
        ]

        result = client.embed("text")

        expected_value = 1 / math.sqrt(DIMENSIONS)

        assert result == pytest.approx(
            [expected_value] * DIMENSIONS
        )
        assert client._client.models.embed_content.call_count == 2

    def test_5xx_exhausted_raises_unavailable(self):
        client = make_client(max_retries=1)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        assert client._client.models.embed_content.call_count == 2


@pytest.mark.django_db
class TestSharedPacing:
    def test_stamps_timestamp_in_cache(self, settings):
        from django.core.cache import cache

        cache.clear()

        client = make_client()
        client._client.models.embed_content.return_value = embed_response(
            [0.0] * DIMENSIONS
        )

        client.embed("text")

        assert cache.get(EMBEDDING_PACING_TIMESTAMP_KEY) is not None

    def test_second_call_sleeps_out_the_remaining_interval(
        self,
        settings,
        monkeypatch,
    ):
        from django.core.cache import cache

        cache.clear()

        client = make_client(min_request_interval=0.85)

        fake_clock = [1_000.4]
        monkeypatch.setattr(time, "time", lambda: fake_clock[0])

        cache.set(
            EMBEDDING_PACING_TIMESTAMP_KEY,
            1_000.0,
            timeout=60,
        )

        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        client._wait_for_pacing_shared()

        assert sleeps == [pytest.approx(0.45)]

    def test_lock_is_released_even_if_request_raises(self, settings):
        from django.core.cache import cache

        cache.clear()

        client = make_client(max_retries=0)
        client._client.models.embed_content.side_effect = FakeAPIError(500)

        with pytest.raises(EmbeddingUnavailableError):
            client.embed("text")

        assert cache.get(EMBEDDING_PACING_LOCK_KEY) is None
