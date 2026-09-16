from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.common.enums import SwipeAction, SwipeSessionStatus, SwipeSessionType
from apps.movies.models import Movie
from apps.swipe_sessions.models import Swipe, SwipeSession, SwipeSessionCandidate


User = get_user_model()


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
def movie(db):
    return Movie.objects.create(
        tmdb_id=1001,
        title="Test Movie",
        release_year=2025,
    )


@pytest.fixture
def another_movie(db):
    return Movie.objects.create(
        tmdb_id=1002,
        title="Another Movie",
        release_year=2024,
    )


@pytest.fixture
def swipe_session(db):
    return SwipeSession.objects.create(
        type=SwipeSessionType.INDIVIDUAL,
        status=SwipeSessionStatus.WAITING,
    )


@pytest.fixture
def another_swipe_session(db):
    return SwipeSession.objects.create(
        type=SwipeSessionType.INDIVIDUAL,
        status=SwipeSessionStatus.WAITING,
    )


@pytest.fixture
def candidate(swipe_session, movie):
    return SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.9,
        position=1,
    )


@pytest.fixture
def another_candidate(swipe_session, another_movie):
    return SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=another_movie,
        score=0.8,
        position=2,
    )


@pytest.fixture
def swipe(user, candidate):
    return Swipe.objects.create(
        user=user,
        candidate=candidate,
        action=SwipeAction.WATCHLIST,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def api_factory():
    return APIRequestFactory()


@pytest.fixture
def authenticated_post(api_factory, user):
    def make_request(path="/", data=None, format="json"):
        request = api_factory.post(path, data=data, format=format)
        force_authenticate(request, user=user)
        return request

    return make_request


@pytest.fixture
def authenticated_get(api_factory, user):
    def make_request(path="/", data=None, format="json"):
        request = api_factory.get(path, data=data, format=format)
        force_authenticate(request, user=user)
        return request

    return make_request