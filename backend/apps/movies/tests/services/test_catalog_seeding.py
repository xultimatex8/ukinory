from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.movies.exceptions import TMDbError, WikidataError
from apps.movies.services.catalog_seeding import (
    CatalogSeedSummary,
    format_seed_summary,
    seed_movie_catalog,
    seed_movie_catalog_deep,
    seed_movie_catalog_light,
)
from apps.movies.services.movie_cache import MovieCacheSummary

PATCH_TARGET = "apps.movies.services.catalog_seeding.{}"


def _patch_pools(popular=None, new_release=None, by_decade=None, by_genre=None):
    return (
        patch(
            PATCH_TARGET.format("discover_popular_tmdb_ids"),
            side_effect=None,
            return_value=popular or [],
        ),
        patch(
            PATCH_TARGET.format("discover_new_release_tmdb_ids"),
            return_value=new_release or [],
        ),
        patch(
            PATCH_TARGET.format("discover_by_decade_tmdb_ids"),
            return_value=by_decade or [],
        ),
        patch(
            PATCH_TARGET.format("discover_by_genre_tmdb_ids"),
            return_value=by_genre or [],
        ),
    )


def _fake_store_result(ids, **kwargs):
    return MovieCacheSummary(
        stored={i: MagicMock() for i in ids},
        already_stored=0,
        without_metadata=0,
    )


class TestSeedMovieCatalogLight:
    def test_only_uses_popular_and_new_release_pools(self):
        patches = _patch_pools(popular=[1, 2], new_release=[2, 3])

        with (
            patches[0],
            patches[1],
            patches[2] as mock_decade,
            patches[3] as mock_genre,
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog_light(MagicMock())

        mock_decade.assert_not_called()
        mock_genre.assert_not_called()
        assert summary.pool_sizes == {"popular": 2, "new_release": 2}
        assert summary.discovered == 3
        assert summary.stored == 3
        assert mock_store.call_count == 2

        for call in mock_store.call_args_list:
            assert call.kwargs["defer_embeddings"] is True

    def test_builds_its_own_client_when_none_given(self):
        patches = _patch_pools()

        with (
            patch(PATCH_TARGET.format("TMDbClient")) as mock_client_cls,
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                return_value=MovieCacheSummary(
                    stored={},
                    already_stored=0,
                    without_metadata=0,
                ),
            ),
        ):
            seed_movie_catalog_light()

        mock_client_cls.assert_called_once_with()


class TestSeedMovieCatalogDeep:
    def test_only_uses_decade_and_genre_pools(self):
        patches = _patch_pools(by_decade=[10, 20], by_genre=[20, 30])

        with (
            patches[0] as mock_popular,
            patches[1] as mock_new,
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog_deep(MagicMock())

        mock_popular.assert_not_called()
        mock_new.assert_not_called()
        assert summary.pool_sizes == {"by_decade": 2, "by_genre": 2}
        assert summary.discovered == 3
        assert summary.stored == 3

        for call in mock_store.call_args_list:
            assert call.kwargs["defer_embeddings"] is True


class TestSeedMovieCatalogIncrementalStorage:
    def test_stores_after_each_pool_not_only_at_the_end(self):
        patches = _patch_pools(popular=[1, 2], new_release=[3])
        store_calls = []

        def fake_store(ids, **kwargs):
            assert kwargs["defer_embeddings"] is True
            store_calls.append(set(ids))
            return _fake_store_result(ids, **kwargs)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=fake_store,
            ),
        ):
            seed_movie_catalog_light(MagicMock())

        assert store_calls == [{1, 2}, {3}]

    def test_a_failing_pool_does_not_lose_movies_already_stored_by_earlier_pools(
        self,
    ):
        with (
            patch(
                PATCH_TARGET.format("discover_popular_tmdb_ids"),
                return_value=[1, 2],
            ),
            patch(
                PATCH_TARGET.format("discover_new_release_tmdb_ids"),
                side_effect=TMDbError("rate limited"),
            ),
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog_light(MagicMock())

        mock_store.assert_called_once_with({1, 2}, defer_embeddings=True)
        assert summary.stored == 2
        assert summary.failed_pools == ["new_release"]

    def test_full_sweep_survives_a_failing_pool_among_several(self):
        with (
            patch(
                PATCH_TARGET.format("discover_popular_tmdb_ids"),
                return_value=[1],
            ),
            patch(
                PATCH_TARGET.format("discover_new_release_tmdb_ids"),
                return_value=[2],
            ),
            patch(
                PATCH_TARGET.format("discover_by_decade_tmdb_ids"),
                side_effect=TMDbError("boom"),
            ),
            patch(
                PATCH_TARGET.format("discover_by_genre_tmdb_ids"),
                return_value=[3],
            ),
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog(MagicMock())

        assert summary.discovered == 3
        assert summary.stored == 3
        assert summary.failed_pools == ["by_decade"]
        assert summary.pool_sizes["by_decade"] == 0

        assert mock_store.call_count == 3
        assert mock_store.call_args_list[0].kwargs["defer_embeddings"] is True
        assert mock_store.call_args_list[1].kwargs["defer_embeddings"] is True

    def test_avoids_re_storing_ids_already_handled_by_an_earlier_pool(self):
        patches = _patch_pools(popular=[1, 2], new_release=[2, 3])
        store_calls = []

        def fake_store(ids, **kwargs):
            assert kwargs["defer_embeddings"] is True
            store_calls.append(set(ids))
            return _fake_store_result(ids, **kwargs)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=fake_store,
            ),
        ):
            summary = seed_movie_catalog_light(MagicMock())

        assert store_calls == [{1, 2}, {3}]
        assert summary.discovered == 3


class TestFormatSeedSummary:
    def test_includes_pool_breakdown_and_totals(self):
        summary = CatalogSeedSummary(
            discovered=10,
            stored=8,
            already_stored=0,
            without_metadata=2,
            pool_sizes={"popular": 5, "new_release": 5},
        )

        text = format_seed_summary(summary)

        assert "Discovered 10" in text
        assert "popular=5" in text
        assert "new_release=5" in text
        assert "stored 8" in text
        assert "2 had no Wikidata metadata coverage" in text
        assert "Failed pools" not in text

    def test_mentions_failed_pools_when_present(self):
        summary = CatalogSeedSummary(
            discovered=5,
            stored=5,
            already_stored=0,
            without_metadata=0,
            pool_sizes={"popular": 5},
            failed_pools=["new_release"],
        )

        text = format_seed_summary(summary)

        assert "Failed pools (skipped): new_release" in text


class TestSeedFromPoolsDetails:
    @pytest.mark.parametrize("error", [WikidataError("boom"), TMDbError("boom")])
    def test_an_enrichment_error_skips_the_pool_and_retries_its_ids_later(self, error):
        with (
            patch(PATCH_TARGET.format("discover_popular_tmdb_ids"), return_value=[1, 2]),
            patch(PATCH_TARGET.format("discover_new_release_tmdb_ids"), return_value=[2, 3]),
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=[error, _fake_store_result([2, 3])],
            ) as mock_store,
        ):
            summary = seed_movie_catalog_light(MagicMock())

        assert [call.args[0] for call in mock_store.call_args_list] == [{1, 2}, {2, 3}]
        assert summary.failed_pools == ["popular"]
        assert summary.pool_sizes == {"popular": 2, "new_release": 2}
        assert summary.discovered == 2
        assert summary.stored == 2

    def test_an_empty_pool_does_not_trigger_any_storage(self):
        patches = _patch_pools(popular=[], new_release=[])

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(PATCH_TARGET.format("fetch_and_store_movies")) as mock_store,
        ):
            summary = seed_movie_catalog_light(MagicMock())

        mock_store.assert_not_called()
        assert summary.pool_sizes == {"popular": 0, "new_release": 0}
        assert summary.discovered == 0
        assert summary.failed_pools == []

    def test_already_stored_and_without_metadata_are_summed_over_the_pools(self):
        patches = _patch_pools(popular=[1, 2], new_release=[3])

        def store(ids, **kwargs):
            return MovieCacheSummary(
                stored={i: MagicMock() for i in ids},
                already_stored=2,
                without_metadata=1,
            )

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(PATCH_TARGET.format("fetch_and_store_movies"), side_effect=store),
        ):
            summary = seed_movie_catalog_light(MagicMock())

        assert summary.already_stored == 4
        assert summary.without_metadata == 2
        assert summary.stored == 3

    def test_every_pool_function_receives_the_given_client(self):
        client = MagicMock()
        patches = _patch_pools(popular=[1], new_release=[2], by_decade=[3], by_genre=[4])

        with (
            patches[0] as popular,
            patches[1] as new_release,
            patches[2] as by_decade,
            patches[3] as by_genre,
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ),
        ):
            seed_movie_catalog(client)

        for pool in (popular, new_release, by_decade, by_genre):
            pool.assert_called_once_with(client)

    def test_pool_size_counts_the_raw_ids_but_storage_gets_unique_ones(self):
        patches = _patch_pools(popular=[1, 1, 2])

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog_light(MagicMock())

        assert summary.pool_sizes["popular"] == 3
        mock_store.assert_called_once_with({1, 2}, defer_embeddings=True)

    def test_full_seed_walks_the_four_pools_in_order_and_always_defers_embeddings(self):
        patches = _patch_pools(popular=[1], new_release=[2], by_decade=[3], by_genre=[4])

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ) as mock_store,
        ):
            summary = seed_movie_catalog(MagicMock())

        assert list(summary.pool_sizes) == ["popular", "new_release", "by_decade", "by_genre"]
        assert [call.args[0] for call in mock_store.call_args_list] == [{1}, {2}, {3}, {4}]
        assert all(call.kwargs["defer_embeddings"] is True for call in mock_store.call_args_list)

    @pytest.mark.parametrize(
        ("seed", "label"),
        [
            (seed_movie_catalog_light, "light"),
            (seed_movie_catalog_deep, "deep"),
            (seed_movie_catalog, "full"),
        ],
    )
    def test_start_and_finish_are_logged(self, seed, label, caplog):
        patches = _patch_pools()

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch(PATCH_TARGET.format("fetch_and_store_movies")),
            caplog.at_level("INFO"),
        ):
            seed(MagicMock())

        assert f"Starting {label} movie catalog seed" in caplog.text
        assert f"Finished {label} movie catalog seed" in caplog.text

    def test_a_failed_pool_is_reported_in_the_log(self, caplog):
        with (
            patch(PATCH_TARGET.format("discover_popular_tmdb_ids"), return_value=[1]),
            patch(
                PATCH_TARGET.format("discover_new_release_tmdb_ids"),
                side_effect=TMDbError("rate limited"),
            ),
            patch(
                PATCH_TARGET.format("fetch_and_store_movies"),
                side_effect=_fake_store_result,
            ),
            caplog.at_level("WARNING"),
        ):
            seed_movie_catalog_light(MagicMock())

        assert "Skipping pool 'new_release' after a TMDb error" in caplog.text
        assert "rate limited" in caplog.text


class TestFormatSeedSummaryDetails:
    def test_exact_text_without_failures(self):
        summary = CatalogSeedSummary(
            discovered=10,
            stored=8,
            already_stored=1,
            without_metadata=2,
            pool_sizes={"popular": 5, "new_release": 5},
        )

        assert format_seed_summary(summary) == (
            "Discovered 10 candidate(s) [popular=5, new_release=5]; "
            "stored 8; already stored 1; 2 had no Wikidata metadata coverage."
        )

    def test_several_failed_pools_are_listed_in_order(self):
        summary = CatalogSeedSummary(
            discovered=0,
            stored=0,
            already_stored=0,
            without_metadata=0,
            pool_sizes={"by_decade": 0, "by_genre": 0},
            failed_pools=["by_decade", "by_genre"],
        )

        assert format_seed_summary(summary).endswith(
            " Failed pools (skipped): by_decade, by_genre."
        )

    def test_no_pools_gives_empty_brackets(self):
        summary = CatalogSeedSummary(
            discovered=0, stored=0, already_stored=0, without_metadata=0, pool_sizes={}
        )

        assert "Discovered 0 candidate(s) []" in format_seed_summary(summary)
