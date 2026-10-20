from contextlib import ExitStack
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
    _MatchOutcome,
    _collect_film_keys,
    _film_key,
    _match_films,
    _merge_rating_sources,
    _needs_embedding,
    _parse_date,
    _parse_rating,
    _parse_year,
    _resolve_one,
    persist_letterboxd_records,
    persist_ratings,
    persist_watchlist,
)
from apps.library.models import Rating, WatchlistEntry, WatchlistSource
from apps.movies.exceptions import MovieMatchNotFound, TMDbUnavailableError
from apps.movies.models import Movie
from apps.movies.services.movie_cache import find_cached_movie
from apps.movies.dtos.movie_summary import MovieCacheSummary


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
            matches, summary = _match_films(client, {("Dune", 2021)}, set())

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
            matches, summary = _match_films(client, {("Dune", 2021)}, set())

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
            return_value=MovieCacheSummary(
                stored={438631: movie},
                already_stored=0,
                without_metadata=0,
            ),
        ) as mock_fetch_and_store:
            matches, summary = _match_films(client, {("Dune", 2021)}, set())

        mock_fetch_and_store.assert_called_once_with(
            {438631}, defer_embeddings=True
        )
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
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=MovieCacheSummary(
                stored={},
                already_stored=0,
                without_metadata=1,
            )
        ):
            matches, summary = _match_films(client, {("Dune", 2021)}, set())

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
            return_value=MovieCacheSummary(
                stored={
                    438631: movie_dune,
                    348: movie_alien,
                },
                already_stored=0,
                without_metadata=0,
            ),
        ) as mock_fetch_and_store:
            matches, summary = _match_films(
                client, {("Dune", 2021), ("Alien", 1979)}, set()
            )

        mock_fetch_and_store.assert_called_once_with(
            {438631, 348}, defer_embeddings=True
        )
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
            return_value=MovieCacheSummary(
                stored={438631: movie},
                already_stored=0,
                without_metadata=0,
            ),
        ) as mock_fetch_and_store:
            matches, summary = _match_films(
                client, {("Dune", 2021), ("Dune (Alternate Cut)", 2021)}, set()
            )

        mock_fetch_and_store.assert_called_once_with({438631}, defer_embeddings=True)
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
            matches, summary = _match_films(
                client, {("Obscure Short", 2021)}, set()
            )

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
                client, {("Dune", 2021), ("Alien", 1979)}, set()
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
            matches, summary = _match_films(client, set(), set())

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


@pytest.fixture
def stub_movie_storage():
    with patch(
        PATCH_TARGET.format("fetch_and_store_movies"),
        return_value=MovieCacheSummary(
            stored={}, already_stored=0, without_metadata=0
        ),
    ) as mock:
        yield mock


@pytest.mark.django_db
class TestPersistRatings:
    def test_creates_rating(self, user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        count = persist_ratings(user, csvs, movie_matches={})

        assert count == 1
        assert Rating.objects.count() == 1

        rating = Rating.objects.get(user=user, title="Dune", release_year=2021)
        assert rating.rating == 4.5
        assert rating.watched_date is None
        assert rating.liked is False
        assert rating.movie is None

    def test_links_matched_movie(self, user):
        movie = Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        persist_ratings(user, csvs, movie_matches={("Dune", 2021): movie})

        rating = Rating.objects.get(user=user, title="Dune", release_year=2021)
        assert rating.movie_id == movie.id

    def test_creates_combined_rating(self, user):
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

        count = persist_ratings(user, csvs, movie_matches={})

        assert count == 1
        rating = Rating.objects.get(user=user, title="Dune", release_year=2021)
        assert rating.rating == 5.0
        assert rating.watched_date == date(2025, 6, 20)
        assert rating.liked is True

    def test_updates_existing_rating(self, user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        persist_ratings(user, csvs, movie_matches={})

        csvs[RATINGS_CSV][0]["Rating"] = "5"
        count = persist_ratings(user, csvs, movie_matches={})

        assert count == 1
        assert Rating.objects.filter(
            user=user, title="Dune", release_year=2021
        ).count() == 1
        rating = Rating.objects.get(user=user, title="Dune", release_year=2021)
        assert rating.rating == 5.0

    def test_persists_multiple_films(self, user):
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

        count = persist_ratings(user, csvs, movie_matches={})

        assert count == 2
        assert Rating.objects.count() == 2

    def test_does_not_duplicate_same_film(self, user):
        csvs = {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}

        persist_ratings(user, csvs, movie_matches={})
        persist_ratings(user, csvs, movie_matches={})

        assert Rating.objects.filter(
            user=user, title="Dune", release_year=2021
        ).count() == 1


@pytest.mark.django_db
class TestPersistWatchlist:
    def test_creates_entry(self, user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        count = persist_watchlist(user, rows, movie_matches={})

        assert count == 1
        assert WatchlistEntry.objects.count() == 1
        entry = WatchlistEntry.objects.get(
            user=user, title="Dune", release_year=2021
        )
        assert entry.added_date == date(2025, 1, 15)
        assert entry.source == WatchlistSource.IMPORTED
        assert entry.movie is None

    def test_links_matched_movie(self, user):
        movie = Movie.objects.create(tmdb_id=1, title="Dune", release_year=2021)
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        persist_watchlist(user, rows, movie_matches={("Dune", 2021): movie})

        entry = WatchlistEntry.objects.get(
            user=user, title="Dune", release_year=2021
        )
        assert entry.movie_id == movie.id

    def test_updates_existing_entry(self, user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]
        persist_watchlist(user, rows, movie_matches={})

        rows[0]["Date"] = "2025-02-20"
        count = persist_watchlist(user, rows, movie_matches={})

        assert count == 1
        entry = WatchlistEntry.objects.get(
            user=user, title="Dune", release_year=2021
        )
        assert entry.added_date == date(2025, 2, 20)

    def test_does_not_duplicate_same_film(self, user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "2025-01-15"}]

        persist_watchlist(user, rows, movie_matches={})
        persist_watchlist(user, rows, movie_matches={})

        assert WatchlistEntry.objects.filter(
            user=user, title="Dune", release_year=2021
        ).count() == 1

    def test_skips_invalid_rows(self, user):
        rows = [
            {"Name": "", "Year": "2021"},
            {"Name": "Dune", "Year": "invalid"},
            {"Name": "Alien", "Year": "1979", "Date": "2025-01-15"},
        ]

        count = persist_watchlist(user, rows, movie_matches={})

        assert count == 1
        assert WatchlistEntry.objects.count() == 1
        assert WatchlistEntry.objects.filter(title="Alien", release_year=1979).exists()

    def test_with_invalid_date(self, user):
        rows = [{"Name": "Dune", "Year": "2021", "Date": "invalid"}]

        count = persist_watchlist(user, rows, movie_matches={})

        assert count == 1
        entry = WatchlistEntry.objects.get(
            user=user, title="Dune", release_year=2021
        )
        assert entry.added_date is None


@pytest.mark.django_db
@pytest.mark.usefixtures("stub_movie_storage")
class TestPersistLetterboxdRecords:
    def test_with_watchlist(self, user, no_tmdb_matches):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
                WATCHLIST_CSV: [
                    {"Name": "Alien", "Year": "1979", "Date": "2025-01-01"}
                ],
            }
        )

        persisted, movie_summary = persist_letterboxd_records(user, result)

        assert persisted == {"ratings": 1, "watchlist": 1}
        assert Rating.objects.filter(
            user=user, title="Dune", release_year=2021
        ).exists()
        assert WatchlistEntry.objects.filter(
            user=user, title="Alien", release_year=1979
        ).exists()
        assert movie_summary.matched == 0
        assert set(movie_summary.unmatched) == {"Dune (2021)", "Alien (1979)"}

    def test_without_watchlist(self, user, no_tmdb_matches):
        result = ExtractionResult(
            csvs={RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        )

        persisted, _ = persist_letterboxd_records(user, result)

        assert persisted == {"ratings": 1}
        assert WatchlistEntry.objects.count() == 0

    def test_with_empty_result(self, user):
        result = ExtractionResult(csvs={})

        persisted, movie_summary = persist_letterboxd_records(user, result)

        assert persisted == {"ratings": 0}
        assert Rating.objects.count() == 0
        assert WatchlistEntry.objects.count() == 0
        assert movie_summary.matched == 0
        assert movie_summary.unmatched == []

    def test_constructs_and_uses_a_tmdb_client_for_matching(self, user):
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
            persist_letterboxd_records(user, result)

        mock_match_movie.assert_called_once_with(fake_client, "Dune", 2021)

    def test_same_film_across_ratings_and_watchlist_is_matched_once(
        self, user
    ):
        movie = Movie.objects.create(
            tmdb_id=1,
            title="Dune",
            release_year=2021,
        )

        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}],
                WATCHLIST_CSV: [{"Name": "Dune", "Year": "2021"}],
            }
        )

        with patch(
            PATCH_TARGET.format("find_cached_movie"),
            return_value=movie,
        ) as mock_find_cached_movie:
            persisted, movie_summary = persist_letterboxd_records(
                user,
                result,
            )

        mock_find_cached_movie.assert_called_once_with("Dune", 2021)

        assert persisted == {
            "ratings": 1,
            "watchlist": 1,
        }

        assert movie_summary.matched == 1
        assert movie_summary.unmatched == []
        assert movie_summary.without_metadata == []
        assert movie_summary.tmdb_error is None

        rating = Rating.objects.get(
            user=user,
            title="Dune",
            release_year=2021,
        )
        assert rating.movie_id == movie.id

        watchlist_entry = WatchlistEntry.objects.get(
            user=user,
            title="Dune",
            release_year=2021,
        )
        assert watchlist_entry.movie_id == movie.id

    def test_a_systemic_tmdb_failure_does_not_block_csv_persistence(
        self, user
    ):
        result = ExtractionResult(
            csvs={RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "4.5"}]}
        )

        with patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=TMDbUnavailableError("TMDb is down"),
        ):
            persisted, movie_summary = persist_letterboxd_records(user, result)

        assert persisted == {"ratings": 1}
        assert Rating.objects.filter(
            user=user, title="Dune", release_year=2021
        ).exists()
        assert movie_summary.tmdb_error == "TMDb is down"

    def test_films_needing_wikidata_are_resolved_in_one_batched_call(
        self, user
    ):
        movie_dune = Movie.objects.create(
            tmdb_id=111, title="Dune", release_year=2021
        )
        movie_alien = Movie.objects.create(
            tmdb_id=348, title="Alien", release_year=1979
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
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            side_effect=[
                MovieCacheSummary(
                    stored={111: movie_dune},
                    already_stored=0,
                    without_metadata=0,
                ),
                MovieCacheSummary(
                    stored={348: movie_alien},
                    already_stored=0,
                    without_metadata=0,
                ),
            ],
        ) as mock_fetch_and_store, patch(
            PATCH_TARGET.format("DEFAULT_MAX_HISTORY_MOVIES"), 1
        ):
            persisted, movie_summary = persist_letterboxd_records(user, result)

        assert mock_fetch_and_store.call_count == 2
        mock_fetch_and_store.assert_any_call({111})
        mock_fetch_and_store.assert_any_call({348}, defer_embeddings=True)
        assert movie_summary.matched == 2
        assert persisted == {"ratings": 1, "watchlist": 1}

    def test_only_the_top_rated_films_are_embedded_synchronously(
        self, user
    ):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [
                    {"Name": "Dune", "Year": "2021", "Rating": "5"},
                    {"Name": "Alien", "Year": "1979", "Rating": "3"},
                ]
            }
        )
        tmdb_ids = {"Dune": 438631, "Alien": 348}

        with patch(
            PATCH_TARGET.format("DEFAULT_MAX_HISTORY_MOVIES"), 1
        ), patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=lambda _c, title, _y: fake_match(tmdb_id=tmdb_ids[title]),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"), return_value=None
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=MovieCacheSummary(
                stored={}, already_stored=0, without_metadata=0
            ),
        ) as mock_fetch:
            persist_letterboxd_records(user, result)

        mock_fetch.assert_any_call({438631})
        mock_fetch.assert_any_call({348}, defer_embeddings=True)


def test_needs_embedding_is_false_when_a_batch_is_already_pending():
    movie = make_movie()
    movie.embedding = None
    movie.embedding_batch_id = 5

    assert _needs_embedding(movie) is False


def test_needs_embedding_is_true_without_vector_or_batch():
    movie = make_movie()
    movie.embedding = None
    movie.embedding_batch_id = None

    assert _needs_embedding(movie) is True


def stored_summary(stored=None):
    return MovieCacheSummary(
        stored=stored or {}, already_stored=0, without_metadata=0
    )


def test_merge_rating_sources_blank_rating_row_does_not_create_entry():
    entries = _merge_rating_sources(
        {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": ""}]}
    )

    assert entries == {}


def test_merge_rating_sources_diary_rating_overrides_ratings_csv():
    entries = _merge_rating_sources(
        {
            RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "3.0"}],
            DIARY_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "4.5",
                    "Watched Date": "2024-01-01",
                }
            ],
        }
    )

    assert entries[("Dune", 2021)].rating == 4.5


def test_merge_rating_sources_dated_diary_row_wins_over_undated_one():
    entries = _merge_rating_sources(
        {
            DIARY_CSV: [
                {"Name": "Dune", "Year": "2021", "Rating": "2.0", "Watched Date": ""},
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "4.0",
                    "Watched Date": "2024-01-01",
                },
            ]
        }
    )

    entry = entries[("Dune", 2021)]
    assert entry.rating == 4.0
    assert entry.watched_date == date(2024, 1, 1)


def test_merge_rating_sources_diary_with_invalid_date_keeps_rating_without_date():
    entries = _merge_rating_sources(
        {
            DIARY_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "3.5",
                    "Watched Date": "not-a-date",
                }
            ]
        }
    )

    entry = entries[("Dune", 2021)]
    assert entry.rating == 3.5
    assert entry.watched_date is None


def test_merge_rating_sources_strips_title_whitespace():
    entries = _merge_rating_sources(
        {WATCHED_CSV: [{"Name": "  Dune  ", "Year": "2021"}]}
    )

    assert set(entries) == {("Dune", 2021)}


class TestResolveOne:
    def test_cache_hit_by_title_and_year(self):
        movie = make_movie()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=movie
        ), patch(PATCH_TARGET.format("match_movie")) as mock_match_movie:
            outcome = _resolve_one(MagicMock(), ("Dune", 2021))

        assert outcome == _MatchOutcome(key=("Dune", 2021), cached_movie=movie)
        mock_match_movie.assert_not_called()

    def test_unknown_film_is_flagged_as_not_found(self):
        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=MovieMatchNotFound("Dune", 2021),
        ):
            outcome = _resolve_one(MagicMock(), ("Dune", 2021))

        assert outcome.not_found is True
        assert outcome.cached_movie is None
        assert outcome.pending_tmdb_id is None
        assert outcome.tmdb_error is None

    def test_tmdb_failure_is_reported_as_error_message(self):
        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=TMDbUnavailableError("TMDb is down"),
        ):
            outcome = _resolve_one(MagicMock(), ("Dune", 2021))

        assert outcome.tmdb_error == "TMDb is down"
        assert outcome.not_found is False

    def test_match_is_resolved_to_cached_movie_by_tmdb_id(self):
        movie = make_movie()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ), patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"),
            return_value=movie,
        ) as mock_by_id:
            outcome = _resolve_one(MagicMock(), ("Dune", 2021))

        mock_by_id.assert_called_once_with(438631)
        assert outcome.cached_movie is movie
        assert outcome.pending_tmdb_id is None

    def test_uncached_match_is_returned_as_pending_tmdb_id(self):
        client = MagicMock()

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=None
        ), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ) as mock_match_movie, patch(
            PATCH_TARGET.format("find_cached_movie_by_tmdb_id"),
            return_value=None,
        ):
            outcome = _resolve_one(client, ("Dune", 2021))

        mock_match_movie.assert_called_once_with(client, "Dune", 2021)
        assert outcome.pending_tmdb_id == 438631
        assert outcome.cached_movie is None


class TestMatchFilmsPriority:
    def _no_cache(self):
        stack = ExitStack()
        stack.enter_context(
            patch(PATCH_TARGET.format("find_cached_movie"), return_value=None)
        )
        stack.enter_context(
            patch(
                PATCH_TARGET.format("find_cached_movie_by_tmdb_id"),
                return_value=None,
            )
        )
        return stack

    def test_priority_film_is_stored_without_deferring_embeddings(self):
        movie = make_movie()

        with self._no_cache(), patch(
            PATCH_TARGET.format("match_movie"),
            return_value=fake_match(tmdb_id=438631),
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=stored_summary({438631: movie}),
        ) as mock_fetch:
            matches, summary = _match_films(
                MagicMock(), {("Dune", 2021)}, {("Dune", 2021)}
            )

        mock_fetch.assert_called_once_with({438631})
        assert matches[("Dune", 2021)] is movie
        assert summary.matched == 1

    def test_priority_and_regular_films_are_fetched_in_separate_calls(self):
        tmdb_ids = {"Dune": 438631, "Alien": 348}

        with self._no_cache(), patch(
            PATCH_TARGET.format("match_movie"),
            side_effect=lambda _c, title, _y: fake_match(tmdb_id=tmdb_ids[title]),
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=stored_summary(),
        ) as mock_fetch:
            _match_films(
                MagicMock(),
                {("Dune", 2021), ("Alien", 1979)},
                {("Dune", 2021)},
            )

        assert mock_fetch.call_count == 2
        mock_fetch.assert_any_call({438631})
        mock_fetch.assert_any_call({348}, defer_embeddings=True)

    def test_cached_priority_film_without_embedding_is_sent_for_embedding(self):
        movie = make_movie()
        movie.tmdb_id = 438631
        movie.embedding = None
        movie.embedding_batch_id = None

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=movie
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=stored_summary(),
        ) as mock_fetch:
            matches, summary = _match_films(
                MagicMock(), {("Dune", 2021)}, {("Dune", 2021)}
            )

        mock_fetch.assert_called_once_with({438631})
        assert matches[("Dune", 2021)] is movie
        assert summary.matched == 1

    def test_cached_priority_film_with_embedding_is_not_fetched_again(self):
        movie = make_movie()
        movie.tmdb_id = 438631
        movie.embedding = [0.1, 0.2]
        movie.embedding_batch_id = None

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=movie
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch:
            _match_films(MagicMock(), {("Dune", 2021)}, {("Dune", 2021)})

        mock_fetch.assert_not_called()

    def test_cached_regular_film_without_embedding_is_not_fetched(self):
        movie = make_movie()
        movie.tmdb_id = 438631
        movie.embedding = None
        movie.embedding_batch_id = None

        with patch(
            PATCH_TARGET.format("find_cached_movie"), return_value=movie
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ) as mock_fetch:
            _match_films(MagicMock(), {("Dune", 2021)}, set())

        mock_fetch.assert_not_called()

    def test_films_before_a_systemic_failure_keep_their_match(self):
        alien = make_movie(title="Alien", release_year=1979)

        def cached(title, _year):
            return alien if title == "Alien" else None

        def match(_client, title, _year):
            if title == "Dune":
                raise TMDbUnavailableError("TMDb is down")
            return fake_match(tmdb_id=1995)

        with patch(
            PATCH_TARGET.format("find_cached_movie"), side_effect=cached
        ), patch(
            PATCH_TARGET.format("match_movie"), side_effect=match
        ), patch(
            PATCH_TARGET.format("fetch_and_store_movies")
        ):
            matches, summary = _match_films(
                MagicMock(),
                {("Alien", 1979), ("Dune", 2021), ("Heat", 1995)},
                set(),
            )

        assert matches == {("Alien", 1979): alien}
        assert summary.matched == 1
        assert summary.unmatched == ["Dune (2021)", "Heat (1995)"]
        assert summary.tmdb_error == "TMDb is down"


@pytest.mark.django_db
class TestPersistRatingsDetails:
    def test_stores_watched_date_liked_flag_and_rating(self, user):
        csvs = {
            DIARY_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "4.0",
                    "Watched Date": "2024-03-01",
                }
            ],
            LIKED_CSV: [{"Name": "Dune", "Year": "2021"}],
        }

        persist_ratings(user, csvs, {})

        rating = Rating.objects.get(user=user, title="Dune")
        assert rating.rating == 4.0
        assert rating.watched_date == date(2024, 3, 1)
        assert rating.liked is True
        assert rating.movie is None

    def test_watched_only_film_is_stored_without_rating(self, user):
        count = persist_ratings(
            user,
            {WATCHED_CSV: [{"Name": "Dune", "Year": "2021"}]},
            {},
        )

        assert count == 1
        rating = Rating.objects.get(user=user, title="Dune")
        assert rating.rating is None
        assert rating.liked is False

    def test_empty_csvs_create_nothing(self, user):
        assert persist_ratings(user, {}, {}) == 0
        assert Rating.objects.count() == 0

    def test_does_not_touch_other_users_ratings(
        self, user, another_user
    ):
        other = another_user
        Rating.objects.create(
            user=other, title="Dune", release_year=2021, rating=1.0, liked=False
        )

        persist_ratings(
            user,
            {RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "5.0"}]},
            {},
        )

        assert Rating.objects.get(user=other, title="Dune").rating == 1.0
        assert Rating.objects.get(user=user, title="Dune").rating == 5.0


@pytest.mark.django_db
class TestPersistWatchlistDetails:
    def test_marks_entries_as_imported_and_stores_added_date(self, user):
        persist_watchlist(
            user,
            [{"Name": "Alien", "Year": "1979", "Date": "2025-01-01"}],
            {},
        )

        entry = WatchlistEntry.objects.get(user=user, title="Alien")
        assert entry.source == WatchlistSource.IMPORTED
        assert entry.added_date == date(2025, 1, 1)
        assert entry.movie is None

    def test_empty_rows_create_nothing(self, user):
        assert persist_watchlist(user, [], {}) == 0
        assert WatchlistEntry.objects.count() == 0

    def test_last_duplicate_row_wins(self, user):
        count = persist_watchlist(
            user,
            [
                {"Name": "Alien", "Year": "1979", "Date": "2024-01-01"},
                {"Name": "Alien", "Year": "1979", "Date": "2025-06-01"},
            ],
            {},
        )

        assert count == 1
        entry = WatchlistEntry.objects.get(user=user, title="Alien")
        assert entry.added_date == date(2025, 6, 1)

    def test_does_not_touch_other_users_entries(
        self, user, another_user
    ):
        other = another_user
        WatchlistEntry.objects.create(
            user=other,
            title="Alien",
            release_year=1979,
            source=WatchlistSource.IMPORTED,
        )

        persist_watchlist(
            user, [{"Name": "Alien", "Year": "1979", "Date": ""}], {}
        )

        assert WatchlistEntry.objects.filter(title="Alien").count() == 2


@pytest.mark.django_db
class TestPersistLetterboxdRecordsPipeline:
    def _pipeline(self, tmdb_ids):
        stack = ExitStack()
        stack.enter_context(
            patch(PATCH_TARGET.format("find_cached_movie"), return_value=None)
        )
        stack.enter_context(
            patch(
                PATCH_TARGET.format("match_movie"),
                side_effect=lambda _c, title, _y: fake_match(
                    tmdb_id=tmdb_ids[title]
                ),
            )
        )
        stack.enter_context(
            patch(
                PATCH_TARGET.format("find_cached_movie_by_tmdb_id"),
                return_value=None,
            )
        )
        return stack

    def test_liked_films_take_priority_over_higher_rated_ones(
        self, user
    ):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [
                    {"Name": "Dune", "Year": "2021", "Rating": "5"},
                    {"Name": "Alien", "Year": "1979", "Rating": "3"},
                ],
                LIKED_CSV: [{"Name": "Alien", "Year": "1979"}],
            }
        )

        with patch(
            PATCH_TARGET.format("DEFAULT_MAX_HISTORY_MOVIES"), 1
        ), self._pipeline({"Dune": 438631, "Alien": 348}), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=stored_summary(),
        ) as mock_fetch:
            persist_letterboxd_records(user, result)

        mock_fetch.assert_any_call({348})
        mock_fetch.assert_any_call({438631}, defer_embeddings=True)

    def test_unrated_films_are_never_priority(self, user):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "5"}],
                WATCHED_CSV: [{"Name": "Alien", "Year": "1979"}],
            }
        )

        with patch(
            PATCH_TARGET.format("DEFAULT_MAX_HISTORY_MOVIES"), 5
        ), self._pipeline({"Dune": 438631, "Alien": 348}), patch(
            PATCH_TARGET.format("fetch_and_store_movies"),
            return_value=stored_summary(),
        ) as mock_fetch:
            persist_letterboxd_records(user, result)

        mock_fetch.assert_any_call({438631})
        mock_fetch.assert_any_call({348}, defer_embeddings=True)

    def test_ratings_are_rolled_back_when_watchlist_persistence_fails(
        self, user, no_tmdb_matches
    ):
        result = ExtractionResult(
            csvs={
                RATINGS_CSV: [{"Name": "Dune", "Year": "2021", "Rating": "5"}],
                WATCHLIST_CSV: [
                    {"Name": "Alien", "Year": "1979", "Date": "2025-01-01"}
                ],
            }
        )

        with patch(
            PATCH_TARGET.format("persist_watchlist"),
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError):
                persist_letterboxd_records(user, result)

        assert Rating.objects.count() == 0
