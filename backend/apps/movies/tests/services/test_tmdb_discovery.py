from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from apps.movies.exceptions import TMDbError
from apps.movies.services.tmdb_discovery import (
    discover_by_decade_tmdb_ids,
    discover_by_genre_tmdb_ids,
    discover_new_release_tmdb_ids,
    discover_popular_tmdb_ids,
    fetch_movie_genre_ids,
)


def make_client(*get_return_values):
    client = MagicMock()
    client.get.side_effect = list(get_return_values)
    return client


def page(results, total_pages=1):
    return {"results": results, "total_pages": total_pages}


def movie(tmdb_id):
    return {"id": tmdb_id}


class TestDiscoverPopularTmdbIds:
    def test_collects_ids_from_a_single_page(self):
        client = make_client(page([movie(1), movie(2)], total_pages=1))

        ids = discover_popular_tmdb_ids(client, max_pages=25)

        assert ids == [1, 2]

    def test_paginates_until_total_pages_reached(self):
        client = make_client(
            page([movie(1)], total_pages=2),
            page([movie(2)], total_pages=2),
        )

        ids = discover_popular_tmdb_ids(client, max_pages=25)

        assert ids == [1, 2]
        assert client.get.call_count == 2

    def test_stops_at_max_pages_even_if_more_are_available(self):
        client = make_client(
            page([movie(1)], total_pages=10),
            page([movie(2)], total_pages=10),
        )

        ids = discover_popular_tmdb_ids(client, max_pages=2)

        assert ids == [1, 2]
        assert client.get.call_count == 2

    def test_stops_early_when_a_page_comes_back_empty(self):
        client = make_client(page([], total_pages=25))

        ids = discover_popular_tmdb_ids(client, max_pages=25)

        assert ids == []
        assert client.get.call_count == 1

    def test_sorts_by_popularity_and_filters_low_vote_counts(self):
        client = make_client(page([]))

        discover_popular_tmdb_ids(client, max_pages=1, min_vote_count=42)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["sort_by"] == "popularity.desc"
        assert kwargs["params"]["vote_count.gte"] == 42

    def test_uses_settings_defaults_when_not_specified(self):
        client = make_client(page([]))

        discover_popular_tmdb_ids(client)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["vote_count.gte"] == 50
        assert client.get.call_count == 1

    def test_excludes_adult_content(self):
        client = make_client(page([]))

        discover_popular_tmdb_ids(client, max_pages=1)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["include_adult"] == "false"


class TestDiscoverNewReleaseTmdbIds:
    def test_filters_by_recent_release_date_window(self):
        client = make_client(page([]))

        discover_new_release_tmdb_ids(
            client, max_pages=1, window_days=30, today=date(2026, 9, 13)
        )

        _, kwargs = client.get.call_args
        assert kwargs["params"]["primary_release_date.gte"] == "2026-08-14"
        assert kwargs["params"]["primary_release_date.lte"] == "2026-09-13"

    def test_sorts_by_release_date_descending(self):
        client = make_client(page([]))

        discover_new_release_tmdb_ids(client, max_pages=1)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["sort_by"] == "primary_release_date.desc"

    def test_uses_a_lower_vote_count_floor_than_the_popular_pool(self):
        client = make_client(page([]))

        discover_new_release_tmdb_ids(client, max_pages=1)

        _, kwargs = client.get.call_args
        assert kwargs["params"]["vote_count.gte"] == 25

    def test_collects_ids_across_pages(self):
        client = make_client(
            page([movie(10)], total_pages=2),
            page([movie(20)], total_pages=2),
        )

        ids = discover_new_release_tmdb_ids(client, max_pages=25)

        assert ids == [10, 20]

    def test_uses_settings_defaults_when_not_specified(self):
        client = make_client(page([]))

        discover_new_release_tmdb_ids(
            client, max_pages=1, today=date(2026, 9, 13)
        )

        _, kwargs = client.get.call_args
        assert kwargs["params"]["primary_release_date.gte"] == "2026-03-17"
        assert kwargs["params"]["vote_count.gte"] == 25


class TestDecadeBuckets:
    def test_splits_range_into_ten_year_chunks(self):
        from apps.movies.services.tmdb_discovery import _decade_buckets

        buckets = _decade_buckets(1990, 2015)

        assert buckets == [(1990, 1999), (2000, 2009), (2010, 2015)]

    def test_snaps_start_year_down_to_the_decade(self):
        from apps.movies.services.tmdb_discovery import _decade_buckets

        buckets = _decade_buckets(1995, 1995)

        assert buckets == [(1990, 1995)]


class TestDiscoverByDecadeTmdbIds:
    def test_makes_one_query_per_decade(self):
        client = make_client(
            page([movie(1)]),
            page([movie(2)]),
        )

        ids = discover_by_decade_tmdb_ids(
            client, start_year=1900, end_year=1919, max_pages_per_decade=1
        )

        assert ids == [1, 2]
        assert client.get.call_count == 2

    def test_sorts_by_rating_not_popularity(self):
        client = make_client(page([]))

        discover_by_decade_tmdb_ids(
            client, start_year=1950, end_year=1950, max_pages_per_decade=1
        )

        _, kwargs = client.get.call_args
        assert kwargs["params"]["sort_by"] == "vote_average.desc"

    def test_scopes_each_bucket_to_its_decade(self):
        client = make_client(page([]), page([]))

        discover_by_decade_tmdb_ids(
            client, start_year=1990, end_year=2005, max_pages_per_decade=1
        )

        first_call_kwargs = client.get.call_args_list[0].kwargs
        second_call_kwargs = client.get.call_args_list[1].kwargs
        assert first_call_kwargs["params"]["primary_release_date.gte"] == "1990-01-01"
        assert first_call_kwargs["params"]["primary_release_date.lte"] == "1999-12-31"
        assert second_call_kwargs["params"]["primary_release_date.gte"] == "2000-01-01"
        assert second_call_kwargs["params"]["primary_release_date.lte"] == "2005-12-31"

    def test_defaults_to_configured_start_year_through_current_year(
        self, settings, monkeypatch
    ):
        import apps.movies.services.tmdb_discovery as discovery_module

        class FixedDate(date):
            @classmethod
            def today(cls):
                return date(2026, 1, 1)

        monkeypatch.setattr(discovery_module, "date", FixedDate)
        client = MagicMock()
        client.get.return_value = page([])

        discover_by_decade_tmdb_ids(client, max_pages_per_decade=1)

        expected_calls = 10
        assert client.get.call_count == expected_calls


class TestFetchMovieGenreIds:
    def test_returns_genre_ids(self):
        client = make_client(
            {"genres": [{"id": 28, "name": "Action"}, {"id": 35, "name": "Comedy"}]}
        )

        genre_ids = fetch_movie_genre_ids(client)

        assert genre_ids == [28, 35]

    def test_missing_genres_key_returns_empty_list(self):
        client = make_client({})

        assert fetch_movie_genre_ids(client) == []


class TestDiscoverByGenreTmdbIds:
    def test_fetches_genres_when_not_provided(self):
        client = make_client(
            {"genres": [{"id": 28, "name": "Action"}]},
            page([movie(1)]),
        )

        ids = discover_by_genre_tmdb_ids(client, max_pages_per_genre=1)

        assert ids == [1]

    def test_uses_explicit_genre_ids_without_fetching(self):
        client = make_client(page([movie(1)]), page([movie(2)]))

        ids = discover_by_genre_tmdb_ids(
            client, genre_ids=[28, 35], max_pages_per_genre=1
        )

        assert ids == [1, 2]
        assert client.get.call_count == 2

    def test_scopes_each_query_to_its_genre(self):
        client = make_client(page([]), page([]))

        discover_by_genre_tmdb_ids(
            client, genre_ids=[28, 99], max_pages_per_genre=1
        )

        first_call_kwargs = client.get.call_args_list[0].kwargs
        second_call_kwargs = client.get.call_args_list[1].kwargs
        assert first_call_kwargs["params"]["with_genres"] == "28"
        assert second_call_kwargs["params"]["with_genres"] == "99"

    def test_sorts_by_popularity(self):
        client = make_client(page([]))

        discover_by_genre_tmdb_ids(
            client, genre_ids=[28], max_pages_per_genre=1
        )

        _, kwargs = client.get.call_args
        assert kwargs["params"]["sort_by"] == "popularity.desc"


class TestDiscoverByDecadeTmdbIdsResilience:
    def test_a_failing_decade_is_skipped_not_fatal(self):
        client = make_client(
            TMDbError("boom"),
            page([movie(2)]),
        )

        ids = discover_by_decade_tmdb_ids(
            client, start_year=1900, end_year=1919, max_pages_per_decade=1
        )

        assert ids == [2]

    def test_all_decades_failing_returns_empty_list_not_raise(self):
        client = MagicMock()
        client.get.side_effect = TMDbError("boom")

        ids = discover_by_decade_tmdb_ids(
            client, start_year=1900, end_year=1909, max_pages_per_decade=1
        )

        assert ids == []


class TestDiscoverByGenreTmdbIdsResilience:
    def test_a_failing_genre_is_skipped_not_fatal(self):
        client = make_client(
            TMDbError("boom"),
            page([movie(5)]),
        )

        ids = discover_by_genre_tmdb_ids(
            client, genre_ids=[28, 99], max_pages_per_genre=1
        )

        assert ids == [5]
