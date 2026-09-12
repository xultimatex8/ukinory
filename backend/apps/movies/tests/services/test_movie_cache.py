from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.movies.models import Genre, Movie
from apps.movies.services.movie_cache import (
    fetch_and_store_movies,
    find_cached_movie,
    find_cached_movie_by_tmdb_id,
)


def fake_match(tmdb_id=438631, title="Dune", release_year=2021, popularity=100.0):
    match = MagicMock()
    match.tmdb_id = tmdb_id
    match.title = title
    match.release_year = release_year
    match.popularity = popularity
    match.is_ambiguous = False
    return match


def fake_metadata(tmdb_id=438631, **overrides) -> dict:
    metadata = {
        "wikidata_id": f"Q{tmdb_id}",
        "title": "Dune",
        "release_year": 2021,
        "wikidata_description": "2021 film directed by Denis Villeneuve",
        "runtime": 155,
        "original_language": "English",
        "directors": ["Denis Villeneuve"],
        "cast": ["Timothée Chalamet"],
        "genres": [{"wikidata_id": "Q471839", "name": "Science Fiction"}],
    }
    metadata.update(overrides)
    return metadata


@pytest.mark.django_db
class TestFindCachedMovie:
    def test_returns_movie_by_title_and_year(self):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)

        movie = find_cached_movie("Dune", 2021)

        assert movie is not None
        assert movie.tmdb_id == 1

    def test_is_case_insensitive(self):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)

        assert find_cached_movie("DUNE", 2021) is not None

    def test_returns_none_when_not_cached(self):
        assert find_cached_movie("Dune", 2021) is None

    def test_year_mismatch_is_a_miss(self):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)

        assert find_cached_movie("Dune", 1984) is None


@pytest.mark.django_db
class TestFindCachedMovieByTmdbId:
    def test_returns_movie_by_tmdb_id(self):
        Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)

        movie = find_cached_movie_by_tmdb_id(438631)

        assert movie is not None
        assert movie.title == "Dune"

    def test_returns_none_when_not_cached(self):
        assert find_cached_movie_by_tmdb_id(438631) is None


@pytest.mark.django_db
class TestFetchAndStoreMovies:
    def test_empty_input_returns_empty_dict_without_calling_wikidata(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata"
        ) as mock_fetch_batch:
            result = fetch_and_store_movies([])

        assert result == {}
        mock_fetch_batch.assert_not_called()

    def test_single_batch_call_for_all_ids(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata",
            return_value={
                438631: fake_metadata(),
                11: fake_metadata(tmdb_id=11, title="Star Wars", release_year=1977),
            },
        ) as mock_fetch_batch:
            result = fetch_and_store_movies([438631, 11])

        mock_fetch_batch.assert_called_once()
        args, _ = mock_fetch_batch.call_args
        assert args[1] == [11, 438631]
        assert set(result.keys()) == {438631, 11}

    def test_dedupes_repeated_tmdb_ids_before_calling_wikidata(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata",
            return_value={438631: fake_metadata()},
        ) as mock_fetch_batch:
            fetch_and_store_movies([438631, 438631, 438631])

        args, _ = mock_fetch_batch.call_args
        assert args[1] == [438631]

    def test_stores_every_resolved_movie(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata",
            return_value={
                438631: fake_metadata(title="Dune", release_year=2021),
                11: fake_metadata(tmdb_id=11, title="Star Wars", release_year=1977),
            },
        ):
            result = fetch_and_store_movies([438631, 11])

        assert Movie.objects.count() == 2
        assert result[438631].title == "Dune"
        assert result[11].title == "Star Wars"

    def test_ids_without_wikidata_coverage_are_absent_not_errors(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata",
            return_value={438631: fake_metadata()},
        ):
            result = fetch_and_store_movies([438631, 999999])

        assert 438631 in result
        assert 999999 not in result
        assert Movie.objects.count() == 1

    def test_reuses_genre_rows_across_the_batch(self):
        with patch(
            "apps.movies.services.movie_cache.fetch_movies_metadata",
            return_value={
                438631: fake_metadata(
                    title="Dune",
                    genres=[{"wikidata_id": "Q471839", "name": "Science Fiction"}],
                ),
                12345: fake_metadata(
                    tmdb_id=12345,
                    title="Another Sci-Fi Film",
                    genres=[{"wikidata_id": "Q471839", "name": "Science Fiction"}],
                ),
            },
        ):
            result = fetch_and_store_movies([438631, 12345])

        assert Genre.objects.count() == 1
        assert result[438631].genres.get().name == "Science Fiction"
        assert result[12345].genres.get().name == "Science Fiction"
