from datetime import date

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.library.models import WatchlistEntry
from apps.library.services.export_watchlist import watchlist_to_csv


@pytest.mark.django_db
def test_watchlist_to_csv_empty_watchlist():
    entries = MagicMock()
    entries.select_related.return_value.order_by.return_value = []

    user = SimpleNamespace(
        watchlist_entries=entries,
    )

    result = watchlist_to_csv(user)

    assert result == "Title,Year\r\n"


@pytest.mark.django_db
def test_watchlist_to_csv_single_entry():
    entry = SimpleNamespace(
        title="Dune: Part Two",
        release_year=2024,
    )

    entries = MagicMock()
    entries.select_related.return_value.order_by.return_value = [entry]

    user = SimpleNamespace(
        watchlist_entries=entries,
    )

    result = watchlist_to_csv(user)

    assert result == "Title,Year\r\nDune: Part Two,2024\r\n"


@pytest.mark.django_db
def test_watchlist_to_csv_entry_without_release_year():
    entry = SimpleNamespace(
        title="Unknown Movie",
        release_year=None,
    )

    entries = MagicMock()
    entries.select_related.return_value.order_by.return_value = [entry]

    user = SimpleNamespace(
        watchlist_entries=entries,
    )

    result = watchlist_to_csv(user)

    assert result == "Title,Year\r\nUnknown Movie,\r\n"


@pytest.mark.django_db
def test_watchlist_to_csv_multiple_entries():
    entries_data = [
        SimpleNamespace(title="Dune: Part Two", release_year=2024),
        SimpleNamespace(title="Inception", release_year=2010),
    ]

    entries = MagicMock()
    entries.select_related.return_value.order_by.return_value = entries_data

    user = SimpleNamespace(
        watchlist_entries=entries,
    )

    result = watchlist_to_csv(user)

    assert result == (
        "Title,Year\r\n"
        "Dune: Part Two,2024\r\n"
        "Inception,2010\r\n"
    )


@pytest.mark.django_db
def test_watchlist_to_csv_uses_expected_query():
    entries = MagicMock()
    ordered_entries = entries.select_related.return_value.order_by.return_value
    ordered_entries.__iter__.return_value = []

    user = SimpleNamespace(
        watchlist_entries=entries,
    )

    watchlist_to_csv(user)

    entries.select_related.assert_called_once_with("movie")
    entries.select_related.return_value.order_by.assert_called_once_with(
        "-added_date",
        "title",
    )


@pytest.mark.django_db
def test_watchlist_to_csv_orders_newest_first_then_by_title(user):
    for title, year, added in [
        ("Zodiac", 2007, date(2025, 1, 2)),
        ("Alien", 1979, date(2025, 1, 2)),
        ("Heat", 1995, date(2025, 3, 1)),
        ("Dune", 2021, date(2024, 12, 31)),
    ]:
        WatchlistEntry.objects.create(
            user=user, title=title, release_year=year, added_date=added
        )

    result = watchlist_to_csv(user)

    assert result.splitlines() == [
        "Title,Year",
        "Heat,1995",
        "Alien,1979",
        "Zodiac,2007",
        "Dune,2021",
    ]


@pytest.mark.django_db
def test_watchlist_to_csv_only_includes_the_users_entries(user, another_user):
    WatchlistEntry.objects.create(
        user=user, title="Dune", release_year=2021, added_date=date(2025, 1, 1)
    )
    WatchlistEntry.objects.create(
        user=another_user, title="Alien", release_year=1979, added_date=date(2025, 1, 1)
    )

    assert watchlist_to_csv(user) == "Title,Year\r\nDune,2021\r\n"


@pytest.mark.django_db
def test_watchlist_to_csv_quotes_titles_with_commas_and_quotes(user):
    WatchlistEntry.objects.create(
        user=user,
        title='Dune, "Part Two"',
        release_year=2024,
        added_date=date(2025, 1, 1),
    )

    assert watchlist_to_csv(user) == (
        'Title,Year\r\n"Dune, ""Part Two""",2024\r\n'
    )


@pytest.mark.django_db
def test_watchlist_to_csv_keeps_unicode_titles_and_blank_unknown_years(user):
    WatchlistEntry.objects.create(
        user=user, title="Amélie", release_year=None, added_date=date(2025, 1, 1)
    )

    assert watchlist_to_csv(user) == "Title,Year\r\nAmélie,\r\n"
