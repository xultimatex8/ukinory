from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from apps.imports.constants import (
    DIARY_CSV,
    LIKED_CSV,
    RATINGS_CSV,
    WATCHED_CSV,
    WATCHLIST_CSV,
)
from apps.imports.dtos.extraction_result import ExtractionResult
from apps.imports.services.letterboxd_persistence import (
    _collect_film_keys,
    _film_key,
    _match_films,
    _merge_rating_sources,
    _parse_date,
    _parse_rating,
    _parse_year,
    persist_letterboxd_records,
    persist_ratings,
    persist_watchlist,
)
from apps.library.models import Rating, WatchlistEntry, WatchlistSource
from apps.movies.exceptions import MovieMatchNotFound, TMDbUnavailableError
from apps.movies.models import Movie
from apps.movies.services.movie_cache import find_cached_movie


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024", 2024),
        ("1999", 1999),
        ("0", 0),
        ("", None),
        (None, None),
        ("invalid", None),
        ("2024.5", None),
    ],
)
def test_parse_year(value, expected):
    assert _parse_year(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-01-15", date(2024, 1, 15)),
        ("1999-12-31", date(1999, 12, 31)),
        ("2000-02-29", date(2000, 2, 29)),
        ("", None),
        (None, None),
        ("15-01-2024", None),
        ("invalid", None),
    ],
)
def test_parse_date(value, expected):
    assert _parse_date(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", 4.0),
        ("4.5", 4.5),
        ("0", 0.0),
        ("10", 10.0),
        ("", None),
        (None, None),
        ("invalid", None),
    ],
)
def test_parse_rating(value, expected):
    assert _parse_rating(value) == expected


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"Name": "Dune", "Year": "2021"}, ("Dune", 2021)),
        ({"Name": "  Dune  ", "Year": "2021"}, ("Dune", 2021)),
        ({"Name": "Dune", "Year": "2021", "Rating": "5"}, ("Dune", 2021)),
        ({"Name": "", "Year": "2021"}, None),
        ({"Name": "Dune", "Year": ""}, None),
        ({"Name": "Dune", "Year": "invalid"}, None),
        ({"Year": "2021"}, None),
        ({"Name": "Dune"}, None),
    ],
)
def test_film_key(row, expected):
    assert _film_key(row) == expected


def test_merge_rating_sources_from_watched():
    csvs = {WATCHED_CSV: [{"Name": "Dune", "Year": "2021"}]}

    result = _merge_rating_sources(csvs)

    assert len(result) == 1
    entry = result[("Dune", 2021)]
    assert entry.title == "Dune"
    assert entry.year == 2021
    assert entry.rating is None
    assert entry.watched_date is None
    assert entry.liked is False


def test_merge_rating_sources_from_ratings():
    csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

    result = _merge_rating_sources(csvs)

    entry = result[("Dune", 2021)]
    assert entry.rating == 4.5


def test_merge_rating_sources_from_likes():
    csvs = {LIKED_CSV: [{"Name": "Dune", "Year": "2021"}]}

    result = _merge_rating_sources(csvs)

    assert result[("Dune", 2021)].liked is True


def test_merge_rating_sources_combines_sources():
    csvs = {
        WATCHED_CSV: [{"Name": "Dune", "Year": "2021"}],
        RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
        LIKED_CSV: [{"Name": "Dune", "Year": "2021"}],
    }

    result = _merge_rating_sources(csvs)

    entry = result[("Dune", 2021)]
    assert entry.rating == 4.5
    assert entry.liked is True


def test_merge_rating_sources_uses_latest_diary_entry():
    csvs = {
        DIARY_CSV: [
            {"Name": "Dune", "Year": "2021", "Rating": "3", "Watched Date": "2024-01-10"},
            {"Name": "Dune", "Year": "2021", "Rating": "4.5", "Watched Date": "2025-06-20"},
        ]
    }

    result = _merge_rating_sources(csvs)

    entry = result[("Dune", 2021)]
    assert entry.rating == 4.5
    assert entry.watched_date == date(2025, 6, 20)


def test_merge_rating_sources_ignores_invalid_rows():
    csvs = {
        WATCHED_CSV: [{"Name": "", "Year": "2021"}, {"Name": "Dune", "Year": "invalid"}],
        RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "invalid"}],
        LIKED_CSV: [{"Name": "", "Year": "2021"}],
    }

    assert _merge_rating_sources(csvs) == {}


def test_merge_rating_sources_empty_csvs():
    assert _merge_rating_sources({}) == {}


def test_merge_rating_sources_preserves_rating_when_diary_rating_invalid():
    csvs = {
        RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
        DIARY_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "invalid",
                "Watched Date": "2025-06-20",
            }
        ],
    }

    entry = _merge_rating_sources(csvs)[("Dune", 2021)]

    assert entry.rating == 4.5
    assert entry.watched_date == date(2025, 6, 20)


def test_collect_film_keys_combines_ratings_and_watchlist():
    csvs = {
        RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "5"}],
        WATCHLIST_CSV: [{"Name": "Alien", "Year": "1979"}],
    }

    keys = _collect_film_keys(csvs)

    assert keys == {("Dune", 2021), ("Alien", 1979)}


def test_collect_film_keys_dedupes_film_in_both_ratings_and_watchlist():
    csvs = {
        RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "5"}],
        WATCHLIST_CSV: [{"Name": "Dune", "Year": "2021"}],
    }

    keys = _collect_film_keys(csvs)

    assert keys == {("Dune", 2021)}


def make_movie(**overrides) -> Movie:
    movie = MagicMock(spec=Movie)
    movie.title = overrides.get("title", "Dune")
    movie.release_year = overrides.get("release_year", 2021)
    return movie


def fake_match(tmdb_id=438631, title="Dune", release_year=2021, popularity=100.0):
    match = MagicMock()
    match.tmdb_id = tmdb_id
    match.title = title
    match.release_year = release_year
    match.popularity = popularity
    match.is_ambiguous = False
    return match


PATCH_TARGET = "apps.imports.services.letterboxd_persistence.{}"


class TestMatchFilms:
    """`_match_films` resolves each film against the local cache and, for a
    TMDb match, only defers to Wikidata once for every film that survives
    both cache checks - as a single batched call - instead of one Wikidata
    request per film."""

    def test_cache_hit_by_title_and_year_skips_tmdb_and_wikidata_entirely(self):
        movie = make_movie()
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=movie
        ), patch(
            PATCH_TARGET.format("match_movie")
        ) as mock_match_movie, patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Dune", 2021)})

        assert matches[("Dune", 2021)] is movie
        assert summary.matched == 1
        assert summary.unmatched == []
        assert summary.without_metadata == []
        assert summary.tmdb_error is None
        mock_match_movie.assert_not_called()
        mock_fetch_and_store.assert_not_called()

    def test_cache_hit_by_tmdb_id_skips_the_wikidata_batch(self):
        movie = make_movie()
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=movie
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Dune", 2021)})

        assert matches[("Dune", 2021)] is movie
        assert summary.matched == 1
        mock_fetch_and_store.assert_not_called()

    def test_full_cache_miss_is_resolved_through_the_wikidata_batch(self):
        movie = make_movie()
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value={438631: movie},
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Dune", 2021)})

        mock_fetch_and_store.assert_called_once_with({438631})
        assert matches[("Dune", 2021)] is movie
        assert summary.matched == 1
        assert summary.without_metadata == []

    def test_wikidata_batch_miss_is_recorded_as_without_metadata_not_unmatched(self):
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"), return_value={}
        ):
            matches, summary = _match_films(client, {("Dune", 2021)})

        assert matches == {}
        assert summary.matched == 0
        assert summary.unmatched == []
        assert summary.without_metadata == ["Dune (2021)"]

    def test_multiple_pending_films_are_resolved_in_a_single_wikidata_call(self):
        client = MagicMock()
        movie_dune = make_movie(title="Dune")
        movie_alien = make_movie(title="Alien", release_year=1979)
        tmdb_ids_by_title = {"Dune": 438631, "Alien": 348}

        def fake_match_movie(_client, title, _year):
            return fake_match(tmdb_id=tmdb_ids_by_title[title])

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"), side_effect=fake_match_movie
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value={438631: movie_dune, 348: movie_alien},
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Dune", 2021), ("Alien", 1979)})

        mock_fetch_and_store.assert_called_once_with({438631, 348})
        assert summary.matched == 2
        assert matches[("Dune", 2021)] is movie_dune
        assert matches[("Alien", 1979)] is movie_alien

    def test_same_tmdb_id_from_different_titles_is_deduped_before_the_wikidata_call(
        self,
    ):
        client = MagicMock()
        movie = make_movie()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"), return_value=fake_match(tmdb_id=438631)
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value={438631: movie},
        ) as mock_fetch_and_store:
            matches, summary = _match_films(
                client, {("Dune", 2021), ("Dune (Alternate Cut)", 2021)}
            )

        mock_fetch_and_store.assert_called_once_with({438631})
        assert summary.matched == 2
        assert matches[("Dune", 2021)] is movie
        assert matches[("Dune (Alternate Cut)", 2021)] is movie

    def test_unmatched_film_is_recorded_without_stopping_the_batch(self):
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=MovieMatchNotFound("Obscure Short", 2021),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id")
        ) as mock_find_by_tmdb_id, patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Obscure Short", 2021)})

        assert summary.matched == 0
        assert summary.unmatched == ["Obscure Short (2021)"]
        assert matches == {}
        mock_find_by_tmdb_id.assert_not_called()
        mock_fetch_and_store.assert_not_called()

    def test_systemic_tmdb_failure_stops_further_matching(self):
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=TMDbUnavailableError("TMDb is down"),
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch_and_store:
            matches, summary = _match_films(
                client, {("Dune", 2021), ("Alien", 1979)}
            )

        assert matches == {}
        assert summary.matched == 0
        assert summary.tmdb_error == "TMDb is down"
        assert set(summary.unmatched) == {"Dune (2021)", "Alien (1979)"}
        mock_fetch_and_store.assert_not_called()

    def test_empty_film_keys_returns_empty_summary(self):
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, set())

        assert matches == {}
        assert summary.matched == 0
        assert summary.unmatched == []
        mock_fetch_and_store.assert_not_called()


@pytest.fixture
def no_tmdb_matches():
    with patch(
        PATCH_TARGET.format("match_movie"),
        side_effect=MovieMatchNotFound("unused", None),
    ):
        yield


@pytest.mark.django_db
class TestPersistRatings:
    def test_creates_rating(self, registered_user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        count = persist_ratings(registered_user, csvs, movie_matches={})

        assert count == 1
        assert Rating.objects.count() == 1

        rating = Rating.objects.get(user=registered_user, title="Dune", release_year=2021)
        assert rating.rating == 4.5
        assert rating.watched_date is None
        assert rating.liked is False
        assert rating.movie is None

    def test_links_matched_movie(self, registered_user):
        movie = Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        persist_ratings(registered_user, csvs, movie_matches={("Dune", 2021): movie})

        rating = Rating.objects.get(user=registered_user, title="Dune", release_year=2021)
        assert rating.movie_id == movie.id

    def test_creates_combined_rating(self, registered_user):
        csvs = {
            WATCHED_CSV: [{"Name": "Dune", "Year": "2021"}],
            RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
            DIARY_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "5",
                    "Watched Date": "2025-06-20",
                }
            ],
            LIKED_CSV: [{"Name": "Dune", "Year": "2021"}],
        }

        count = persist_ratings(registered_user, csvs, movie_matches={})

        assert count == 1
        rating = Rating.objects.get(user=registered_user, title="Dune", release_year=2021)
        assert rating.rating == 5.0
        assert rating.watched_date == date(2025, 6, 20)
        assert rating.liked is True

    def test_updates_existing_rating(self, registered_user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        persist_ratings(registered_user, csvs, movie_matches={})

        csvs[RATINGS_CSV][0]["Rating"] = "5"
        count = persist_ratings(registered_user, csvs, movie_matches={})

        assert count == 1
        assert Rating.objects.filter(
            user=registered_user, title="Dune", release_year=2021
        ).count() == 1
        rating = Rating.objects.get(user=registered_user, title="Dune", release_year=2021)
        assert rating.rating == 5.0

    def test_persists_multiple_films(self, registered_user):
        csvs = {
            WATCHED_CSV: [
                {"Name": "Dune", "Year": "2021"},
                {"Name": "Alien", "Year": "1979"},
            ],
            RATINGS_CSV: [
                {"Name": "Dune", "Year": "2021", "Rating": "4.5"},
                {"Name": "Alien", "Year": "1979", "Rating": "5"},
            ],
        }

        count = persist_ratings(registered_user, csvs, movie_matches={})

        assert count == 2
        assert Rating.objects.count() == 2

    def test_does_not_duplicate_same_film(self, registered_user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        persist_ratings(registered_user, csvs, movie_matches={})
        persist_ratings(registered_user, csvs, movie_matches={})

        assert Rating.objects.filter(
            user=registered_user, title="Dune", release_year=2021
        ).count() == 1


@pytest.mark.django_db
class TestPersistWatchlist:
    def test_creates_entry(self, registered_user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        count = persist_watchlist(registered_user, rows, movie_matches={})

        assert count == 1
        assert WatchlistEntry.objects.count() == 1
        entry = WatchlistEntry.objects.get(
            user=registered_user, title="Dune", release_year=2021
        )
        assert entry.added_date == date(2025, 1, 15)
        assert entry.source == WatchlistSource.IMPORTED
        assert entry.movie is None

    def test_links_matched_movie(self, registered_user):
        movie = Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        persist_watchlist(registered_user, rows, movie_matches={("Dune", 2021): movie})

        entry = WatchlistEntry.objects.get(
            user=registered_user, title="Dune", release_year=2021
        )
        assert entry.movie_id == movie.id

    def test_updates_existing_entry(self, registered_user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]
        persist_watchlist(registered_user, rows, movie_matches={})

        rows[0]["Date"] = "2025-02-20"
        count = persist_watchlist(registered_user, rows, movie_matches={})

        assert count == 1
        entry = WatchlistEntry.objects.get(
            user=registered_user, title="Dune", release_year=2021
        )
        assert entry.added_date == date(2025, 2, 20)

    def test_does_not_duplicate_same_film(self, registered_user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        persist_watchlist(registered_user, rows, movie_matches={})
        persist_watchlist(registered_user, rows, movie_matches={})

        assert WatchlistEntry.objects.filter(
            user=registered_user, title="Dune", release_year=2021
        ).count() == 1

    def test_skips_invalid_rows(self, registered_user):
        rows = [
            {"Name": "", "Year": "2021"},
            {"Name": "Dune", "Year": "invalid"},
            {"Name": "Alien", "Year": "1979", "Date": "2025-01-15"},
        ]

        count = persist_watchlist(registered_user, rows, movie_matches={})

        assert count == 1
        assert WatchlistEntry.objects.count() == 1
        assert WatchlistEntry.objects.filter(title="Alien", release_year=1979).exists()

    def test_with_invalid_date(self, registered_user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "invalid"}]

        count = persist_watchlist(registered_user, rows, movie_matches={})

        assert count == 1
        entry = WatchlistEntry.objects.get(
            user=registered_user, title="Dune", release_year=2021
        )
        assert entry.added_date is None


@pytest.mark.django_db
@pytest.mark.usefixtures("no_tmdb_matches")
class TestPersistLetterboxdRecords:
    def test_with_watchlist(self, registered_user):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
                WATCHLIST_CSV: [
                    {"Name": "Alien", "Year": "1979", "Date": "2025-01-01"}
                ],
            }
        )
 
        persisted, movie_summary = persist_letterboxd_records(registered_user, result)
 
        assert persisted == {"ratings": 1, "watchlist": 1}
        assert Rating.objects.filter(
            user=registered_user, title="Dune", release_year=2021
        ).exists()
        assert WatchlistEntry.objects.filter(
            user=registered_user, title="Alien", release_year=1979
        ).exists()
        assert movie_summary.matched == 0
        assert set(movie_summary.unmatched) == {"Dune (2021)", "Alien (1979)"}
 
    def test_without_watchlist(self, registered_user):
        result = ExtractionResult(
            csvs={RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        )
 
        persisted, _ = persist_letterboxd_records(registered_user, result)
 
        assert persisted == {"ratings": 1}
        assert WatchlistEntry.objects.count() == 0
 
    def test_with_empty_result(self, registered_user):
        result = ExtractionResult(csvs={})
 
        persisted, movie_summary = persist_letterboxd_records(registered_user, result)
 
        assert persisted == {"ratings": 0}
        assert Rating.objects.count() == 0
        assert WatchlistEntry.objects.count() == 0
        assert movie_summary.matched == 0
        assert movie_summary.unmatched == []
 
    def test_constructs_and_uses_a_tmdb_client_for_matching(self, registered_user):
        Movie.objects.create(tmdb_id=1, title="Dune (import spelling)", release_year=2021)
        result = ExtractionResult(
            csvs={RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        )
        fake_client = MagicMock()

        with patch(
            "apps.imports.services.letterboxd_persistence.TMDbClient",
            return_value=fake_client,
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=1),
        ) as mock_match_movie:
            persist_letterboxd_records(registered_user, result)

        mock_match_movie.assert_called_once_with(fake_client, "Dune", 2021)

    def test_same_film_across_ratings_and_watchlist_is_matched_once(
        self, registered_user
    ):
        Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
                WATCHLIST_CSV: [{"Name": "Dune", "Year": "2021"}],
            }
        )

        with patch(
            PATCH_TARGET.format("find_cached_movie"), wraps=find_cached_movie
        ) as mock_find_cached_movie:
            persist_letterboxd_records(registered_user, result)

        mock_find_cached_movie.assert_called_once()

    def test_a_systemic_tmdb_failure_does_not_block_csv_persistence(
        self, registered_user
    ):
        result = ExtractionResult(
            csvs={RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        )

        with patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=TMDbUnavailableError("TMDb is down"),
        ):
            persisted, movie_summary = persist_letterboxd_records(registered_user, result)

        assert persisted == {"ratings": 1}
        assert Rating.objects.filter(
            user=registered_user, title="Dune", release_year=2021
        ).exists()
        assert movie_summary.tmdb_error == "TMDb is down"

    def test_films_needing_wikidata_are_resolved_in_one_batched_call(
        self, registered_user
    ):
        movie = Movie.objects.create(
            tmdb_id=438631, title="Dune", release_year=2021
        )
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
                WATCHLIST_CSV: [{"Name": "Alien", "Year": "1979"}],
            }
        )

        def fake_match_movie(_client, title, _year):
            return fake_match(tmdb_id={"Dune": 111, "Alien": 348}[title])

        with patch(
            PATCH_TARGET.format("match_movie"), side_effect=fake_match_movie
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value={348: movie},
        ) as mock_fetch_and_store:
            persisted, movie_summary = persist_letterboxd_records(registered_user, result)

        mock_fetch_and_store.assert_called_once_with({348})
        assert movie_summary.matched == 2
        assert persisted == {"ratings": 1, "watchlist": 1}
