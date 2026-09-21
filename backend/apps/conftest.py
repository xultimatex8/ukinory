from __future__ import annotations

import httpx
import pytest
from requests.adapters import HTTPAdapter
from django.contrib.auth import get_user_model


User = get_user_model()


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
            "A test tried to create a real Gemini client. Mock EmbeddingClient, "
            "JustificationClient or genai.Client in that test."
        )

    monkeypatch.setattr("google.genai.Client", _blocked)


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    def _blocked_requests(self, request, **kwargs):
        raise RuntimeError(
            f"Real HTTP request (requests): {request.method} {request.url}"
        )

    def _blocked_httpx(self, request, **kwargs):
        raise RuntimeError(
            f"Real HTTP request (httpx): {request.method} {request.url}"
        )

    monkeypatch.setattr(HTTPAdapter, "send", _blocked_requests)
    monkeypatch.setattr(httpx.Client, "send", _blocked_httpx)
    monkeypatch.setattr(httpx.AsyncClient, "send", _blocked_httpx)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="TestPassword123!",
        is_guest=False,
    )


@pytest.fixture
def another_user(db):
    return User.objects.create_user(
        email="another@example.com",
        username="anotheruser",
        password="TestPassword123!",
        is_guest=False,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="bob@example.com", 
        username="bob", 
        password="Str0ngP4ssw0rd!"
    )