import pytest
from rest_framework.test import APIClient

from apps.library.models import Rating


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRateMovieView:
    def movie_url(self, tmdb_id):
        return f"/api/library/movies/{tmdb_id}/rating/"

    def test_rates_movie(
        self,
        api_client,
        user,
        movie,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(movie.tmdb_id),
            {
                "rating": 4.5,
                "liked": True,
            },
            format="json",
        )

        assert response.status_code == 200

        rating = Rating.objects.get(
            user=user,
            movie=movie,
        )

        assert rating.rating == 4.5
        assert rating.liked is True

    def test_rates_movie_with_watched_date(
        self,
        api_client,
        user,
        movie,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(movie.tmdb_id),
            {
                "rating": 4.0,
                "liked": True,
                "watched_date": "2026-09-20",
            },
            format="json",
        )

        assert response.status_code == 200

        rating = Rating.objects.get(
            user=user,
            movie=movie,
        )

        assert rating.watched_date.isoformat() == "2026-09-20"

    def test_returns_404_when_movie_does_not_exist(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(999999999),
            {
                "rating": 4.0,
            },
            format="json",
        )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Movie not found.",
        }

    def test_rejects_invalid_data(
        self,
        api_client,
        user,
        movie,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(movie.tmdb_id),
            {
                "rating": 6.0,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_requires_authentication(
        self,
        api_client,
        movie,
    ):
        response = api_client.post(
            self.movie_url(movie.tmdb_id),
            {
                "rating": 4.0,
            },
            format="json",
        )

        assert response.status_code == 401
