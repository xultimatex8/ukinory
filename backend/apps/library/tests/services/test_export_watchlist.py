import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

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
