import pytest
from rest_framework.test import APIClient

from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)



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

    def test_returns_empty_body_on_success(self, api_client, user, movie):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(movie.tmdb_id), {"rating": 3.5}, format="json"
        )

        assert response.status_code == 200
        assert response.data is None

    def test_rating_again_updates_the_same_rating(self, api_client, user, movie):
        api_client.force_authenticate(user=user)

        api_client.post(
            self.movie_url(movie.tmdb_id), {"rating": 2.0}, format="json"
        )
        api_client.post(
            self.movie_url(movie.tmdb_id),
            {"rating": 4.5, "liked": True},
            format="json",
        )

        rating = Rating.objects.get(user=user, movie=movie)
        assert rating.rating == 4.5
        assert rating.liked is True

    def test_liked_defaults_to_false(self, api_client, user, movie):
        api_client.force_authenticate(user=user)

        api_client.post(
            self.movie_url(movie.tmdb_id), {"rating": 4.0}, format="json"
        )

        assert Rating.objects.get(user=user, movie=movie).liked is False

    def test_removes_the_film_from_the_users_watchlist(
        self, api_client, user, movie
    ):
        entry = WatchlistEntry.objects.create(
            user=user, title=movie.title, release_year=movie.release_year
        )
        api_client.force_authenticate(user=user)

        api_client.post(
            self.movie_url(movie.tmdb_id), {"rating": 4.0}, format="json"
        )

        assert not WatchlistEntry.objects.filter(pk=entry.pk).exists()

    def test_does_not_change_another_users_rating(
        self, api_client, user, another_user, movie
    ):
        other = Rating.objects.create(
            user=another_user,
            title=movie.title,
            release_year=movie.release_year,
            movie=movie,
            rating=1.0,
            liked=False,
        )
        api_client.force_authenticate(user=user)

        api_client.post(
            self.movie_url(movie.tmdb_id), {"rating": 5.0}, format="json"
        )

        other.refresh_from_db()
        assert other.rating == 1.0

    @pytest.mark.parametrize(
        "payload",
        [
            {"rating": "abc"},
            {"rating": 4.0, "watched_date": "not-a-date"},
            {"rating": 4.0, "liked": "maybe"},
        ],
    )
    def test_invalid_payloads_are_rejected_without_creating_a_rating(
        self, api_client, user, movie, payload
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.movie_url(movie.tmdb_id), payload, format="json"
        )

        assert response.status_code == 400
        assert not Rating.objects.filter(user=user).exists()

    def test_unknown_movie_does_not_create_a_rating(self, api_client, user):
        api_client.force_authenticate(user=user)

        api_client.post(self.movie_url(999999999), {"rating": 4.0}, format="json")

        assert not Rating.objects.filter(user=user).exists()

    def test_rejects_unsupported_methods(self, api_client, user, movie):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.movie_url(movie.tmdb_id))

        assert response.status_code == 405
