from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.movies.exceptions import EmbeddingUnavailableError
from apps.movies.models import Genre, Movie
from apps.movies.services.embedding_client import DIMENSIONS
from apps.movies.services.movie_cache import (
    MovieCacheSummary,
    fetch_and_store_movies,
    find_cached_movie,
    find_cached_movie_by_tmdb_id,
)

FETCH_TARGET = "apps.movies.services.movie_cache.fetch_movies_metadata"
UNIT_VECTOR = [1.0] + [0.0] * (DIMENSIONS - 1)


@pytest.fixture(autouse=True)
def fake_clients():
    with patch("apps.movies.services.movie_cache.WikidataClient"), patch(
        "apps.movies.services.movie_cache.EmbeddingClient"
    ) as embedding_cls:
        embedding_cls.return_value.embed_many.side_effect = lambda texts: [
            UNIT_VECTOR for _ in texts
        ]
        yield embedding_cls


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
    def test_empty_input_returns_empty_summary_without_calling_wikidata(
        self, fake_clients
    ):
        with patch(FETCH_TARGET) as mock_fetch_batch:
            result = fetch_and_store_movies([])

        assert result == MovieCacheSummary(
            stored={},
            already_stored=0,
            without_metadata=0,
        )
        mock_fetch_batch.assert_not_called()
        fake_clients.assert_not_called()

    def test_single_batch_call_for_all_ids(self):
        with patch(
            FETCH_TARGET,
            return_value={
                438631: fake_metadata(),
                11: fake_metadata(tmdb_id=11, title="Star Wars", release_year=1977),
            },
        ) as mock_fetch_batch:
            result = fetch_and_store_movies([438631, 11])

        mock_fetch_batch.assert_called_once()

        args, _ = mock_fetch_batch.call_args
        assert args[1] == [11, 438631]
        assert set(result.stored.keys()) == {438631, 11}
        assert result.already_stored == 0
        assert result.without_metadata == 0

    def test_dedupes_repeated_tmdb_ids_before_calling_wikidata(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}) as mock_fetch:
            fetch_and_store_movies([438631, 438631, 438631])

        args, _ = mock_fetch.call_args
        assert args[1] == [438631]

    def test_stores_every_resolved_movie(self):
        with patch(
            FETCH_TARGET,
            return_value={
                438631: fake_metadata(title="Dune", release_year=2021),
                11: fake_metadata(tmdb_id=11, title="Star Wars", release_year=1977),
            },
        ):
            result = fetch_and_store_movies([438631, 11])

        assert Movie.objects.count() == 2
        assert result.stored[438631].title == "Dune"
        assert result.stored[11].title == "Star Wars"

    def test_ids_without_wikidata_coverage_are_absent_not_errors(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            result = fetch_and_store_movies([438631, 999999])

        assert 438631 in result.stored
        assert 999999 not in result.stored
        assert result.without_metadata == 1
        assert Movie.objects.count() == 1

    def test_reuses_genre_rows_across_the_batch(self):
        genres = [{"wikidata_id": "Q471839", "name": "Science Fiction"}]
        with patch(
            FETCH_TARGET,
            return_value={
                438631: fake_metadata(title="Dune", genres=genres),
                12345: fake_metadata(
                    tmdb_id=12345, title="Another Sci-Fi Film", genres=genres
                ),
            },
        ):
            result = fetch_and_store_movies([438631, 12345])

        assert Genre.objects.count() == 1
        assert result.stored[438631].genres.get().name == "Science Fiction"
        assert result.stored[12345].genres.get().name == "Science Fiction"

    def test_two_tmdb_ids_sharing_a_wikidata_id_store_only_the_first(self):
        with patch(
            FETCH_TARGET,
            return_value={
                1: fake_metadata(tmdb_id=1, wikidata_id="Q100"),
                2: fake_metadata(tmdb_id=2, wikidata_id="Q100"),
            },
        ):
            result = fetch_and_store_movies([1, 2])

        assert set(result.stored) == {1}
        assert Movie.objects.count() == 1


@pytest.mark.django_db
class TestEmbeddings:
    def test_embeds_synchronously_by_default(self, fake_clients):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            result = fetch_and_store_movies([438631])

        movie = result.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is not None
        assert movie.embedding_source_hash != ""
        assert movie.embedding_source_hash == movie.embedding_target_hash
        fake_clients.return_value.embed_many.assert_called_once()

    def test_deferred_mode_never_builds_an_embedding_client(self, fake_clients):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            result = fetch_and_store_movies([438631], defer_embeddings=True)

        fake_clients.assert_not_called()
        movie = result.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is None
        assert movie.embedding_target_hash != ""
        assert movie.embedding_source_hash != movie.embedding_target_hash

    def test_unchanged_movie_is_counted_as_already_stored(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631])
            second = fetch_and_store_movies([438631])

        assert second.already_stored == 1
        assert second.stored == {}

    def test_unchanged_deferred_movie_is_counted_as_already_stored(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631], defer_embeddings=True)
            second = fetch_and_store_movies([438631], defer_embeddings=True)

        assert second.already_stored == 1
        assert second.stored == {}

    def test_changed_metadata_is_stored_again(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631])

        with patch(
            FETCH_TARGET,
            return_value={438631: fake_metadata(title="Dune: Part One")},
        ):
            second = fetch_and_store_movies([438631])

        assert second.already_stored == 0
        assert second.stored[438631].title == "Dune: Part One"

    def test_movie_is_stored_without_a_vector_when_embedding_is_unavailable(
        self, fake_clients
    ):
        fake_clients.return_value.embed_many.side_effect = EmbeddingUnavailableError(
            "down"
        )

        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            result = fetch_and_store_movies([438631])

        movie = result.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is None
        assert movie.embedding_target_hash != ""
