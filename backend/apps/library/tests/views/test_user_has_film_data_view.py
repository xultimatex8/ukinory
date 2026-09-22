from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.library.models import Rating


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestUserHasFilmDataView:
    url = "/api/library/has-film-data/"

    def test_returns_false_when_user_has_no_film_data(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data is False

    def test_returns_true_when_user_has_rating(
        self,
        api_client,
        user,
        rating,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data is True

    def test_does_not_use_another_users_film_data(
        self,
        api_client,
        user,
        another_user,
        movie,
    ):

        Rating.objects.create(
            user=another_user,
            title=movie.title,
            release_year=movie.release_year,
            movie=movie,
            rating=4.0,
            liked=True,
        )

        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data is False

    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.get(self.url)

        assert response.status_code == 401
