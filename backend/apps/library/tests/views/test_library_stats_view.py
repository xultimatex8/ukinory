from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.library.models import Rating
from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)



@pytest.fixture
def api_client():
    return APIClient()


def _embedding():
    return [0.1] * Movie._meta.get_field("embedding").dimensions


def _rate(user, movie, rating, **kwargs):
    return Rating.objects.create(
        user=user,
        title=movie.title if movie else kwargs.pop("title", "Untitled"),
        release_year=movie.release_year if movie else kwargs.pop("release_year", 2000),
        movie=movie,
        rating=rating,
        liked=kwargs.pop("liked", False),
    )


@pytest.mark.django_db
class TestLibraryStatsView:
    url = "/api/library/stats/"

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.url)

        assert response.status_code == 401

    def test_returns_zero_counts_without_ratings(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == {"rated_total": 0, "rated_with_embedding": 0}

    def test_counts_rated_films_and_those_with_embedding(
        self, api_client, user, movie
    ):
        with_embedding = Movie.objects.create(
            tmdb_id=880001, title="Embedded", release_year=2020
        )
        Movie.objects.filter(pk=with_embedding.pk).update(embedding=_embedding())
        _rate(user, movie, 4.0)
        _rate(user, with_embedding, 3.0)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data == {"rated_total": 2, "rated_with_embedding": 1}

    def test_ignores_films_without_a_rating_value(self, api_client, user, movie):
        _rate(user, movie, None, liked=True)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data == {"rated_total": 0, "rated_with_embedding": 0}

    def test_counts_ratings_without_matched_movie_only_in_total(
        self, api_client, user
    ):
        _rate(user, None, 4.0, title="Unmatched", release_year=1999)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data == {"rated_total": 1, "rated_with_embedding": 0}

    def test_does_not_count_other_users_ratings(
        self, api_client, user, another_user, movie
    ):
        _rate(another_user, movie, 4.0)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.data == {"rated_total": 0, "rated_with_embedding": 0}

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(self.url)

        assert response.status_code == 405
