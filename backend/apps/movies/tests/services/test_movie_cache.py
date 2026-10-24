from __future__ import annotations

import hashlib
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError
from apps.movies.models import Genre, Movie
from apps.movies.services.embedding_client import DEFAULT_SYNC_CHUNK_SIZE, DIMENSIONS
from apps.movies.services.movie_cache import (
    MovieCacheSummary,
    _embed_in_chunks,
    _is_up_to_date,
    _Prepared,
    _store_movie,
    embedding_hash,
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


class TestEmbeddingHash:
    def test_is_the_sha256_hex_digest_of_the_utf8_text(self):
        assert embedding_hash("Dune") == hashlib.sha256(b"Dune").hexdigest()

    def test_is_deterministic(self):
        expected = embedding_hash("Dune")
        actual = embedding_hash("Dune")

        assert actual == expected

    def test_different_texts_have_different_hashes(self):
        assert embedding_hash("Dune") != embedding_hash("Dune ")

    def test_non_ascii_text_is_supported(self):
        assert embedding_hash("Amélie") == hashlib.sha256("Amélie".encode("utf-8")).hexdigest()


class TestIsUpToDate:
    def existing(self, source="", target=""):
        return SimpleNamespace(embedding_source_hash=source, embedding_target_hash=target)

    def test_unknown_movies_are_never_up_to_date(self):
        assert _is_up_to_date(None, "h", defer=False) is False
        assert _is_up_to_date(None, "h", defer=True) is False

    @pytest.mark.parametrize("defer", [False, True])
    def test_a_movie_embedded_from_the_same_text_is_up_to_date(self, defer):
        assert _is_up_to_date(self.existing(source="h"), "h", defer=defer) is True

    def test_a_pending_movie_is_up_to_date_only_when_deferring(self):
        pending = self.existing(source="old", target="h")

        assert _is_up_to_date(pending, "h", defer=True) is True
        assert _is_up_to_date(pending, "h", defer=False) is False

    @pytest.mark.parametrize("defer", [False, True])
    def test_a_movie_with_other_hashes_is_outdated(self, defer):
        assert _is_up_to_date(self.existing(source="a", target="b"), "h", defer=defer) is False


def prepared(count):
    return [_Prepared(i, {}, f"text {i}", f"hash{i}") for i in range(count)]


class TestEmbedInChunks:
    def fake_client(self):
        client = MagicMock()
        client.embed_many.side_effect = lambda texts: [
            [float(text.split()[1])] for text in texts
        ]
        return client

    def test_nothing_to_embed_makes_no_request(self):
        client = self.fake_client()

        assert _embed_in_chunks([], client) == {}

        client.embed_many.assert_not_called()

    def test_items_are_embedded_in_chunks_and_keyed_by_tmdb_id(self):
        client = self.fake_client()
        total = DEFAULT_SYNC_CHUNK_SIZE * 2 + 5

        vectors = _embed_in_chunks(prepared(total), client)

        sizes = [len(call.args[0]) for call in client.embed_many.call_args_list]
        assert sizes == [DEFAULT_SYNC_CHUNK_SIZE, DEFAULT_SYNC_CHUNK_SIZE, 5]
        assert vectors == {i: [float(i)] for i in range(total)}

    def test_an_unavailable_service_stops_and_leaves_the_rest_for_the_batch_job(self, caplog):
        client = self.fake_client()
        good = client.embed_many.side_effect
        client.embed_many.side_effect = [
            good(["text 0"]),
            EmbeddingUnavailableError("down"),
        ]
        items = prepared(DEFAULT_SYNC_CHUNK_SIZE * 3)

        with caplog.at_level(logging.WARNING):
            vectors = _embed_in_chunks(items, client)

        assert client.embed_many.call_count == 2
        assert len(vectors) == 1
        assert f"{DEFAULT_SYNC_CHUNK_SIZE * 2} movie(s) left for the batch job" in caplog.text

    def test_a_bad_chunk_is_skipped_and_the_next_one_is_tried(self, caplog):
        client = self.fake_client()
        ok = client.embed_many.side_effect
        client.embed_many.side_effect = [
            EmbeddingError("bad chunk"),
            ok([f"text {i}" for i in range(DEFAULT_SYNC_CHUNK_SIZE, DEFAULT_SYNC_CHUNK_SIZE + 3)]),
        ]
        items = prepared(DEFAULT_SYNC_CHUNK_SIZE + 3)

        with caplog.at_level(logging.WARNING):
            vectors = _embed_in_chunks(items, client)

        assert set(vectors) == {DEFAULT_SYNC_CHUNK_SIZE, DEFAULT_SYNC_CHUNK_SIZE + 1, DEFAULT_SYNC_CHUNK_SIZE + 2}
        assert "Could not embed a chunk" in caplog.text


@pytest.mark.django_db
class TestStoreMovie:
    def item(self, tmdb_id=1, text_hash="h1", **overrides):
        return _Prepared(
            tmdb_id, fake_metadata(tmdb_id=tmdb_id, **overrides), "text", text_hash
        )

    def test_a_new_movie_is_created_from_the_metadata(self):
        movie = _store_movie(self.item(), None)

        movie.refresh_from_db()
        assert movie.tmdb_id == 1
        assert movie.wikidata_id == "Q1"
        assert movie.title == "Dune"
        assert movie.release_year == 2021
        assert movie.wikidata_description == "2021 film directed by Denis Villeneuve"
        assert movie.runtime == 155
        assert movie.original_language == "English"
        assert movie.directors == ["Denis Villeneuve"]
        assert movie.metadata_fetched_at is not None
        assert movie.embedding_target_hash == "h1"
        assert movie.embedding is None

    def test_a_vector_sets_the_embedding_and_the_source_hash(self):
        movie = _store_movie(self.item(), UNIT_VECTOR)

        movie.refresh_from_db()
        assert movie.embedding is not None
        assert movie.embedding_source_hash == "h1"
        assert movie.embedding_target_hash == "h1"

    def test_updating_without_a_vector_keeps_the_previous_embedding(self):
        _store_movie(self.item(text_hash="old"), UNIT_VECTOR)

        movie = _store_movie(self.item(text_hash="new", title="Dune: Part One"), None)

        movie.refresh_from_db()
        assert movie.title == "Dune: Part One"
        assert movie.embedding is not None
        assert movie.embedding_source_hash == "old"
        assert movie.embedding_target_hash == "new"

    def test_an_existing_movie_is_updated_not_duplicated(self):
        _store_movie(self.item(), None)
        _store_movie(self.item(title="Another title"), None)

        assert Movie.objects.count() == 1
        assert Movie.objects.get().title == "Another title"

    def test_genres_are_replaced_by_the_new_ones(self):
        both = [
            {"wikidata_id": "Q1", "name": "Drama"},
            {"wikidata_id": "Q2", "name": "Comedy"},
        ]
        _store_movie(self.item(genres=both), None)

        movie = _store_movie(self.item(genres=both[1:]), None)

        assert [g.name for g in movie.genres.all()] == ["Comedy"]

    def test_existing_genres_are_reused_and_keep_their_name(self):
        Genre.objects.create(wikidata_id="Q471839", name="Sci-Fi")

        movie = _store_movie(self.item(), None)

        assert Genre.objects.count() == 1
        assert [g.name for g in movie.genres.all()] == ["Sci-Fi"]

    def test_a_movie_without_genres_has_none(self):
        movie = _store_movie(self.item(genres=[]), None)

        assert movie.genres.count() == 0


@pytest.mark.django_db
class TestFetchAndStoreDetails:
    def test_metadata_that_produces_no_embedding_text_is_skipped(self):
        empty = fake_metadata(
            title="", release_year=None, wikidata_description="", genres=[],
            directors=[], original_language="", runtime=None,
        )

        with patch(FETCH_TARGET, return_value={438631: empty}):
            result = fetch_and_store_movies([438631])

        assert result.stored == {}
        assert result.already_stored == 0
        assert result.without_metadata == 0
        assert Movie.objects.count() == 0

    def test_a_duplicated_wikidata_id_is_not_counted_as_missing_metadata(self):
        with patch(
            FETCH_TARGET,
            return_value={
                1: fake_metadata(tmdb_id=1, wikidata_id="Q100"),
                2: fake_metadata(tmdb_id=2, wikidata_id="Q100"),
            },
        ):
            result = fetch_and_store_movies([1, 2])

        assert result.without_metadata == 0

    def test_the_wikidata_client_is_built_once_and_passed_to_the_lookup(self):
        with patch(
            "apps.movies.services.movie_cache.WikidataClient"
        ) as wikidata_cls, patch(FETCH_TARGET, return_value={}) as fetch:
            fetch_and_store_movies([1, 2, 3])

        wikidata_cls.assert_called_once_with()
        assert fetch.call_args.args[0] is wikidata_cls.return_value

    def test_a_chunk_that_cannot_be_embedded_still_stores_the_movie(self, fake_clients):
        fake_clients.return_value.embed_many.side_effect = EmbeddingError("bad")

        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            result = fetch_and_store_movies([438631])

        movie = result.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is None
        assert movie.embedding_target_hash != ""

    def test_many_movies_are_embedded_in_chunks(self, fake_clients):
        count = DEFAULT_SYNC_CHUNK_SIZE + 1
        metadata = {
            i: fake_metadata(tmdb_id=i, title=f"Film {i}") for i in range(1, count + 1)
        }

        with patch(FETCH_TARGET, return_value=metadata):
            result = fetch_and_store_movies(list(metadata))

        assert len(result.stored) == count
        assert fake_clients.return_value.embed_many.call_count == 2

    def test_a_deferred_update_keeps_the_old_vector_but_marks_it_stale(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631])

        with patch(
            FETCH_TARGET, return_value={438631: fake_metadata(title="Dune: Part One")}
        ):
            result = fetch_and_store_movies([438631], defer_embeddings=True)

        movie = result.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is not None
        assert movie.embedding_source_hash != movie.embedding_target_hash

    def test_a_movie_waiting_for_the_batch_job_is_embedded_by_a_synchronous_run(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631], defer_embeddings=True)
            second = fetch_and_store_movies([438631])

        assert second.already_stored == 0
        movie = second.stored[438631]
        movie.refresh_from_db()
        assert movie.embedding is not None
        assert movie.embedding_source_hash == movie.embedding_target_hash

    def test_changed_metadata_updates_the_existing_row(self):
        with patch(FETCH_TARGET, return_value={438631: fake_metadata()}):
            fetch_and_store_movies([438631])
        with patch(
            FETCH_TARGET, return_value={438631: fake_metadata(runtime=160)}
        ):
            fetch_and_store_movies([438631])

        assert Movie.objects.count() == 1
        assert Movie.objects.get().runtime == 160
