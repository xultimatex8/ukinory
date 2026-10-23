from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)


@pytest.fixture
def rating(user, movie):
    return Rating.objects.create(
        user=user,
        title=movie.title,
        release_year=movie.release_year,
        movie=movie,
        rating=4.0,
        liked=True,
    )



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

    def test_returns_true_for_a_liked_film_without_a_rating_value(
        self, api_client, user
    ):
        Rating.objects.create(
            user=user, title="Dune", release_year=2021, rating=None, liked=True
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data is True

    def test_watchlist_entries_do_not_count_as_film_data(self, api_client, user):
        WatchlistEntry.objects.create(user=user, title="Dune", release_year=2021)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data is False

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(self.url)

        assert response.status_code == 405
