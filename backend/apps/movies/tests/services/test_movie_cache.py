from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.movies.exceptions import MovieMatchNotFound
from apps.movies.models import Genre, Movie
from apps.movies.services.movie_cache import get_or_fetch_movie


def fake_match(tmdb_id=438631, title="Dune", release_year=2021, popularity=100.0):
    match = MagicMock()
    match.tmdb_id = tmdb_id
    match.title = title
    match.release_year = release_year
    match.popularity = popularity
    match.is_ambiguous = False
    return match


def fake_metadata(**overrides) -> dict:
    metadata = {
        "tmdb_id": 438631,
        "title": "Dune",
        "release_year": 2021,
        "synopsis": "A noble family...",
        "poster_url": "https://image.tmdb.org/t/p/w500/dune.jpg",
        "vote_average": 8.0,
        "runtime": 155,
        "streaming_providers": {},
        "genres": [{"tmdb_id": 878, "name": "Science Fiction"}],
    }
    metadata.update(overrides)
    return metadata


@pytest.mark.django_db
class TestGetOrFetchMovieCacheHits:
    def test_returns_cached_movie_by_title_and_year_without_calling_tmdb(self):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        client = MagicMock()

        movie = get_or_fetch_movie(client, "Dune", 2021)

        assert movie.tmdb_id == 1
        client.get.assert_not_called()

    def test_title_lookup_is_case_insensitive(self):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        client = MagicMock()

        movie = get_or_fetch_movie(client, "DUNE", 2021)

        assert movie.tmdb_id == 1
        client.get.assert_not_called()

    def test_matches_but_already_cached_by_tmdb_id_skips_metadata_fetch(self):
        Movie.objects.create(tmdb_id=438631, title="Dune (import spelling)", release_year=2021)
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie", return_value=fake_match()
        ) as mock_match, patch(
            "apps.movies.services.movie_cache.fetch_movie_metadata"
        ) as mock_fetch:
            movie = get_or_fetch_movie(client, "Dune (alt title)", 2021)

        mock_match.assert_called_once()
        mock_fetch.assert_not_called()
        assert movie.tmdb_id == 438631


@pytest.mark.django_db
class TestGetOrFetchMovieCacheMiss:
    def test_full_miss_matches_fetches_and_stores(self):
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie", return_value=fake_match()
        ), patch(
            "apps.movies.services.movie_cache.fetch_movie_metadata",
            return_value=fake_metadata(),
        ):
            movie = get_or_fetch_movie(client, "Dune", 2021)

        assert movie.tmdb_id == 438631
        assert movie.title == "Dune"
        assert movie.synopsis == "A noble family..."
        assert Movie.objects.count() == 1

    def test_stores_genres_as_m2m(self):
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie", return_value=fake_match()
        ), patch(
            "apps.movies.services.movie_cache.fetch_movie_metadata",
            return_value=fake_metadata(
                genres=[
                    {"tmdb_id": 878, "name": "Science Fiction"},
                    {"tmdb_id": 12, "name": "Adventure"},
                ]
            ),
        ):
            movie = get_or_fetch_movie(client, "Dune", 2021)

        assert set(movie.genres.values_list("name", flat=True)) == {
            "Science Fiction",
            "Adventure",
        }
        assert Genre.objects.count() == 2

    def test_reuses_existing_genre_rows_instead_of_duplicating(self):
        Genre.objects.create(tmdb_id=878, name="Science Fiction")
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie", return_value=fake_match()
        ), patch(
            "apps.movies.services.movie_cache.fetch_movie_metadata",
            return_value=fake_metadata(
                genres=[{"tmdb_id": 878, "name": "Science Fiction"}]
            ),
        ):
            get_or_fetch_movie(client, "Dune", 2021)

        assert Genre.objects.count() == 1

    def test_not_found_propagates(self):
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie",
            side_effect=MovieMatchNotFound("Some Obscure Title", 2021),
        ):
            with pytest.raises(MovieMatchNotFound):
                get_or_fetch_movie(client, "Some Obscure Title", 2021)

    def test_second_call_for_same_film_hits_cache(self):
        client = MagicMock()

        with patch(
            "apps.movies.services.movie_cache.match_movie", return_value=fake_match()
        ) as mock_match, patch(
            "apps.movies.services.movie_cache.fetch_movie_metadata",
            return_value=fake_metadata(),
        ) as mock_fetch:
            get_or_fetch_movie(client, "Dune", 2021)
            get_or_fetch_movie(client, "Dune", 2021)

        mock_match.assert_called_once()
        mock_fetch.assert_called_once()
