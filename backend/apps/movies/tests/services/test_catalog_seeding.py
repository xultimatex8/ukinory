from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.movies.exceptions import TMDbError
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
        patch(PATCH_TARGET.format("discover_popular_tmdb_ids"), side_effect=None, return_value=popular or []),
        patch(PATCH_TARGET.format("discover_new_release_tmdb_ids"), return_value=new_release or []),
        patch(PATCH_TARGET.format("discover_by_decade_tmdb_ids"), return_value=by_decade or []),
        patch(PATCH_TARGET.format("discover_by_genre_tmdb_ids"), return_value=by_genre or []),
    )


def _fake_store_result(ids):
    return MovieCacheSummary(
        stored={i: MagicMock() for i in ids},
        already_stored=0,
        without_metadata=0,
    )


class TestSeedMovieCatalogLight:
    def test_only_uses_popular_and_new_release_pools(self):
        patches = _patch_pools(popular=[1, 2], new_release=[2, 3])
        with patches[0], patches[1], patches[2] as mock_decade, patches[3] as mock_genre, patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            side_effect=_fake_store_result,
        ) as mock_store:
            summary = seed_movie_catalog_light(MagicMock())

        mock_decade.assert_not_called()
        mock_genre.assert_not_called()
        assert summary.pool_sizes == {"popular": 2, "new_release": 2}
        assert summary.discovered == 3
        assert summary.stored == 3
        assert mock_store.call_count == 2

    def test_builds_its_own_client_when_none_given(self):
        patches = _patch_pools()
        with patch(PATCH_TARGET.format("TMDbClient")) as mock_client_cls, \
             patches[0], patches[1], patches[2], patches[3], patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=MovieCacheSummary(
                stored={},
                already_stored=0,
                without_metadata=0,
            ),
        ):
            seed_movie_catalog_light()

        mock_client_cls.assert_called_once_with()


class TestSeedMovieCatalogDeep:
    def test_only_uses_decade_and_genre_pools(self):
        patches = _patch_pools(by_decade=[10, 20], by_genre=[20, 30])
        with patches[0] as mock_popular, patches[1] as mock_new, patches[2], patches[3], patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            side_effect=_fake_store_result,
        ):
            summary = seed_movie_catalog_deep(MagicMock())

        mock_popular.assert_not_called()
        mock_new.assert_not_called()
        assert summary.pool_sizes == {"by_decade": 2, "by_genre": 2}
        assert summary.discovered == 3
        assert summary.stored == 3


class TestSeedMovieCatalogIncrementalStorage:
    def test_stores_after_each_pool_not_only_at_the_end(self):
        """The whole point: if a later pool blows up, earlier pools must
        already be safely stored."""
        patches = _patch_pools(popular=[1, 2], new_release=[3])
        store_calls = []

        def fake_store(ids):
            store_calls.append(set(ids))
            return _fake_store_result(ids)

        with patches[0], patches[1], patches[2], patches[3], patch(
            PATCH_TARGET.format("fetch_and_store_movies"), side_effect=fake_store
        ):
            seed_movie_catalog_light(MagicMock())

        assert store_calls == [{1, 2}, {3}]

    def test_a_failing_pool_does_not_lose_movies_already_stored_by_earlier_pools(self):
        with patch(
            PATCH_TARGET.format("discover_popular_tmdb_ids"), return_value=[1, 2]
        ), patch(
            PATCH_TARGET.format("discover_new_release_tmdb_ids"),
            side_effect=TMDbError("rate limited"),
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            side_effect=_fake_store_result,
        ) as mock_store:
            summary = seed_movie_catalog_light(MagicMock())

        mock_store.assert_called_once_with({1, 2})
        assert summary.stored == 2
        assert summary.failed_pools == ["new_release"]

    def test_full_sweep_survives_a_failing_pool_among_several(self):
        with patch(
            PATCH_TARGET.format("discover_popular_tmdb_ids"), return_value=[1]
        ), patch(
            PATCH_TARGET.format("discover_new_release_tmdb_ids"), return_value=[2]
        ), patch(
            PATCH_TARGET.format("discover_by_decade_tmdb_ids"),
            side_effect=TMDbError("boom"),
        ), patch(
            PATCH_TARGET.format("discover_by_genre_tmdb_ids"), return_value=[3]
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            side_effect=_fake_store_result,
        ):
            summary = seed_movie_catalog(MagicMock())

        assert summary.discovered == 3
        assert summary.stored == 3
        assert summary.failed_pools == ["by_decade"]
        assert summary.pool_sizes["by_decade"] == 0

    def test_avoids_re_storing_ids_already_handled_by_an_earlier_pool(self):
        patches = _patch_pools(popular=[1, 2], new_release=[2, 3])
        store_calls = []

        def fake_store(ids):
            store_calls.append(set(ids))
            return _fake_store_result(ids)

        with patches[0], patches[1], patches[2], patches[3], patch(
            PATCH_TARGET.format("fetch_and_store_movies"), side_effect=fake_store
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
