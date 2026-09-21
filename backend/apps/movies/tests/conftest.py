from __future__ import annotations

import pytest
from requests.adapters import HTTPAdapter

from apps.movies.models import Movie


@pytest.fixture(autouse=True)
def locmem_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ukinory-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def block_real_gemini(monkeypatch, settings):
    settings.GEMINI_API_KEY = "test-key"

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "A test tried to create a real Gemini client. Mock EmbeddingClient "
            "(or pass defer_embeddings=True) in that test."
        )

    monkeypatch.setattr("apps.movies.services.embedding_client.genai.Client", _blocked)


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    def _blocked(self, request, **kwargs):
        raise RuntimeError(
            f"A test tried to make a real HTTP request: {request.method} {request.url}"
        )

    monkeypatch.setattr(HTTPAdapter, "send", _blocked)


@pytest.fixture
def movie(db):
    return Movie.objects.create(
        tmdb_id=12345,
        title="Test Movie",
        release_year=2020,
        wikidata_description="A test movie.",
        original_language="en",
        runtime=120,
    )
