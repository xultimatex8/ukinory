from datetime import date

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
    _film_key,
    _merge_rating_sources,
    _parse_date,
    _parse_rating,
    _parse_year,
    persist_letterboxd_records,
    persist_ratings,
    persist_watchlist,
)
from apps.library.models import Rating, WatchlistEntry, WatchlistSource


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
        (
            {"Name": "Dune", "Year": "2021"},
            ("Dune", 2021),
        ),
        (
            {"Name": "  Dune  ", "Year": "2021"},
            ("Dune", 2021),
        ),
        (
            {"Name": "Dune", "Year": "2021", "Rating": "5"},
            ("Dune", 2021),
        ),
        (
            {"Name": "", "Year": "2021"},
            None,
        ),
        (
            {"Name": "Dune", "Year": ""},
            None,
        ),
        (
            {"Name": "Dune", "Year": "invalid"},
            None,
        ),
        (
            {"Year": "2021"},
            None,
        ),
        (
            {"Name": "Dune"},
            None,
        ),
    ],
)
def test_film_key(row, expected):
    assert _film_key(row) == expected



def test_merge_rating_sources_from_watched():
    csvs = {
        WATCHED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ]
    }

    result = _merge_rating_sources(csvs)

    assert len(result) == 1

    entry = result[("Dune", 2021)]

    assert entry.title == "Dune"
    assert entry.year == 2021
    assert entry.rating is None
    assert entry.watched_date is None
    assert entry.liked is False


def test_merge_rating_sources_from_ratings():
    csvs = {
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ]
    }

    result = _merge_rating_sources(csvs)

    assert len(result) == 1

    entry = result[("Dune", 2021)]

    assert entry.title == "Dune"
    assert entry.year == 2021
    assert entry.rating == 4.5
    assert entry.watched_date is None
    assert entry.liked is False


def test_merge_rating_sources_from_likes():
    csvs = {
        LIKED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ]
    }

    result = _merge_rating_sources(csvs)

    assert len(result) == 1

    entry = result[("Dune", 2021)]

    assert entry.title == "Dune"
    assert entry.year == 2021
    assert entry.rating is None
    assert entry.watched_date is None
    assert entry.liked is True


def test_merge_rating_sources_combines_sources():
    csvs = {
        WATCHED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ],
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ],
        LIKED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ],
    }

    result = _merge_rating_sources(csvs)

    assert len(result) == 1

    entry = result[("Dune", 2021)]

    assert entry.title == "Dune"
    assert entry.year == 2021
    assert entry.rating == 4.5
    assert entry.watched_date is None
    assert entry.liked is True


def test_merge_rating_sources_uses_latest_diary_entry():
    csvs = {
        DIARY_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "3",
                "Watched Date": "2024-01-10",
            },
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
                "Watched Date": "2025-06-20",
            },
        ]
    }

    result = _merge_rating_sources(csvs)

    assert len(result) == 1

    entry = result[("Dune", 2021)]

    assert entry.rating == 4.5
    assert entry.watched_date == date(2025, 6, 20)


def test_merge_rating_sources_ignores_invalid_rows():
    csvs = {
        WATCHED_CSV: [
            {
                "Name": "",
                "Year": "2021",
            },
            {
                "Name": "Dune",
                "Year": "invalid",
            },
        ],
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "invalid",
            }
        ],
        LIKED_CSV: [
            {
                "Name": "",
                "Year": "2021",
            }
        ],
    }

    result = _merge_rating_sources(csvs)

    assert result == {}


def test_merge_rating_sources_empty_csvs():
    result = _merge_rating_sources({})

    assert result == {}


def test_merge_rating_sources_preserves_rating_when_diary_rating_invalid():
    csvs = {
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ],
        DIARY_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "invalid",
                "Watched Date": "2025-06-20",
            }
        ],
    }

    result = _merge_rating_sources(csvs)

    entry = result[("Dune", 2021)]

    assert entry.rating == 4.5
    assert entry.watched_date == date(2025, 6, 20)



@pytest.mark.django_db
def test_persist_ratings_creates_rating(registered_user):
    csvs = {
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ]
    }

    count = persist_ratings(registered_user, csvs)

    assert count == 1
    assert Rating.objects.count() == 1

    rating = Rating.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert rating.rating == 4.5
    assert rating.watched_date is None
    assert rating.liked is False


@pytest.mark.django_db
def test_persist_ratings_creates_combined_rating(registered_user):
    csvs = {
        WATCHED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ],
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ],
        DIARY_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "5",
                "Watched Date": "2025-06-20",
            }
        ],
        LIKED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            }
        ],
    }

    count = persist_ratings(registered_user, csvs)

    assert count == 1

    rating = Rating.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert rating.rating == 5.0
    assert rating.watched_date == date(2025, 6, 20)
    assert rating.liked is True


@pytest.mark.django_db
def test_persist_ratings_updates_existing_rating(registered_user):
    csvs = {
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ]
    }

    persist_ratings(registered_user, csvs)

    csvs[RATINGS_CSV][0]["Rating"] = "5"

    count = persist_ratings(registered_user, csvs)

    assert count == 1

    assert Rating.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).count() == 1

    rating = Rating.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert rating.rating == 5.0


@pytest.mark.django_db
def test_persist_ratings_persists_multiple_films(registered_user):
    csvs = {
        WATCHED_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
            },
            {
                "Name": "Alien",
                "Year": "1979",
            },
        ],
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            },
            {
                "Name": "Alien",
                "Year": "1979",
                "Rating": "5",
            },
        ],
    }

    count = persist_ratings(registered_user, csvs)

    assert count == 2
    assert Rating.objects.count() == 2


@pytest.mark.django_db
def test_persist_ratings_does_not_duplicate_same_film(registered_user):
    csvs = {
        RATINGS_CSV: [
            {
                "Name": "Dune",
                "Year": "2021",
                "Rating": "4.5",
            }
        ]
    }

    persist_ratings(registered_user, csvs)
    persist_ratings(registered_user, csvs)

    assert Rating.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).count() == 1



@pytest.mark.django_db
def test_persist_watchlist_creates_entry(registered_user):
    rows = [
        {
            "Name": "Dune",
            "Year": "2021",
            "Date": "2025-01-15",
        }
    ]

    count = persist_watchlist(registered_user, rows)

    assert count == 1
    assert WatchlistEntry.objects.count() == 1

    entry = WatchlistEntry.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert entry.added_date == date(2025, 1, 15)
    assert entry.source == WatchlistSource.IMPORTED


@pytest.mark.django_db
def test_persist_watchlist_updates_existing_entry(registered_user):
    rows = [
        {
            "Name": "Dune",
            "Year": "2021",
            "Date": "2025-01-15",
        }
    ]

    persist_watchlist(registered_user, rows)

    rows[0]["Date"] = "2025-02-20"

    count = persist_watchlist(registered_user, rows)

    assert count == 1

    assert WatchlistEntry.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).count() == 1

    entry = WatchlistEntry.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert entry.added_date == date(2025, 2, 20)


@pytest.mark.django_db
def test_persist_watchlist_does_not_duplicate_same_film(registered_user):
    rows = [
        {
            "Name": "Dune",
            "Year": "2021",
            "Date": "2025-01-15",
        }
    ]

    persist_watchlist(registered_user, rows)
    persist_watchlist(registered_user, rows)

    assert WatchlistEntry.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).count() == 1


@pytest.mark.django_db
def test_persist_watchlist_skips_invalid_rows(registered_user):
    rows = [
        {
            "Name": "",
            "Year": "2021",
        },
        {
            "Name": "Dune",
            "Year": "invalid",
        },
        {
            "Name": "Alien",
            "Year": "1979",
            "Date": "2025-01-15",
        },
    ]

    count = persist_watchlist(registered_user, rows)

    assert count == 1
    assert WatchlistEntry.objects.count() == 1

    assert WatchlistEntry.objects.filter(
        title="Alien",
        release_year=1979,
    ).exists()


@pytest.mark.django_db
def test_persist_watchlist_with_invalid_date(registered_user):
    rows = [
        {
            "Name": "Dune",
            "Year": "2021",
            "Date": "invalid",
        }
    ]

    count = persist_watchlist(registered_user, rows)

    assert count == 1

    entry = WatchlistEntry.objects.get(
        user=registered_user,
        title="Dune",
        release_year=2021,
    )

    assert entry.added_date is None



@pytest.mark.django_db
def test_persist_letterboxd_records_with_watchlist(registered_user):
    result = ExtractionResult(
        csvs={
            RATINGS_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "4.5",
                }
            ],
            WATCHLIST_CSV: [
                {
                    "Name": "Alien",
                    "Year": "1979",
                    "Date": "2025-01-01",
                }
            ],
        }
    )

    persisted = persist_letterboxd_records(registered_user, result)

    assert persisted == {
        "ratings": 1,
        "watchlist": 1,
    }

    assert Rating.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).exists()

    assert WatchlistEntry.objects.filter(
        user=registered_user,
        title="Alien",
        release_year=1979,
    ).exists()


@pytest.mark.django_db
def test_persist_letterboxd_records_without_watchlist(registered_user):
    result = ExtractionResult(
        csvs={
            RATINGS_CSV: [
                {
                    "Name": "Dune",
                    "Year": "2021",
                    "Rating": "4.5",
                }
            ],
        }
    )

    persisted = persist_letterboxd_records(registered_user, result)

    assert persisted == {
        "ratings": 1,
    }

    assert Rating.objects.filter(
        user=registered_user,
        title="Dune",
        release_year=2021,
    ).exists()

    assert WatchlistEntry.objects.count() == 0


@pytest.mark.django_db
def test_persist_letterboxd_records_with_empty_result(registered_user):
    result = ExtractionResult(csvs={})

    persisted = persist_letterboxd_records(registered_user, result)

    assert persisted == {
        "ratings": 0,
    }

    assert Rating.objects.count() == 0
    assert WatchlistEntry.objects.count() == 0
