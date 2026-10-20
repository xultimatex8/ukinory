from __future__ import annotations

from datetime import date

import pytest
from django.utils import timezone

from apps.common.enums import WatchlistSource
from apps.library.models import WatchlistEntry
from apps.library.services.watchlist import (
    add_movie,
    remove_movie,
    rows_to_csv,
    saved_movie_ids,
)
from apps.movies.models import Movie


@pytest.fixture
def dune():
    return Movie.objects.create(tmdb_id=990001, title="Dune", release_year=2021)


@pytest.fixture
def alien():
    return Movie.objects.create(tmdb_id=990002, title="Alien", release_year=1979)


def _entry(user, title, year, **kwargs):
    kwargs.setdefault("source", WatchlistSource.IMPORTED)
    return WatchlistEntry.objects.create(
        user=user, title=title, release_year=year, **kwargs
    )


@pytest.mark.django_db
class TestAddMovie:
    def test_creates_entry_for_the_movie(self, user, dune):
        entry = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert entry.user == user
        assert entry.title == "Dune"
        assert entry.release_year == 2021
        assert entry.movie == dune
        assert entry.source == WatchlistSource.COMPARISON_ADDED
        assert entry.added_date == timezone.localdate()

    def test_is_idempotent(self, user, dune):
        first = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)
        second = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert first.pk == second.pk
        assert WatchlistEntry.objects.filter(user=user).count() == 1

    def test_keeps_source_and_date_of_existing_entry(self, user, dune):
        existing = _entry(
            user, "Dune", 2021, movie=dune, added_date=date(2020, 1, 1)
        )

        result = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert result.pk == existing.pk
        existing.refresh_from_db()
        assert existing.source == WatchlistSource.IMPORTED
        assert existing.added_date == date(2020, 1, 1)

    def test_overwrite_replaces_source_date_and_movie(self, user, dune):
        existing = _entry(
            user, "Dune", 2021, movie=None, added_date=date(2020, 1, 1)
        )

        add_movie(
            user, dune, WatchlistSource.COMPARISON_ADDED, overwrite=True
        )

        existing.refresh_from_db()
        assert existing.source == WatchlistSource.COMPARISON_ADDED
        assert existing.added_date == timezone.localdate()
        assert existing.movie == dune

    def test_links_movie_to_matching_entry_without_one(self, user, dune):
        existing = _entry(user, "dune", 2021, movie=None)

        result = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert result.pk == existing.pk
        existing.refresh_from_db()
        assert existing.movie == dune
        assert existing.title == "dune"
        assert WatchlistEntry.objects.filter(user=user).count() == 1

    def test_matches_entry_already_linked_to_the_movie_under_another_title(
        self, user, dune
    ):
        existing = _entry(user, "Dune (import spelling)", 2021, movie=dune)

        result = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert result.pk == existing.pk
        assert WatchlistEntry.objects.filter(user=user).count() == 1

    def test_same_title_with_different_year_is_a_different_film(
        self, user, dune
    ):
        _entry(user, "Dune", 1984, movie=None)

        add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert WatchlistEntry.objects.filter(user=user).count() == 2

    def test_ignores_other_users_entries(self, user, another_user, dune):
        _entry(another_user, "Dune", 2021, movie=dune)

        entry = add_movie(user, dune, WatchlistSource.COMPARISON_ADDED)

        assert entry.user == user
        assert WatchlistEntry.objects.filter(user=another_user).count() == 1
        assert WatchlistEntry.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestRemoveMovie:
    def test_removes_entry_linked_to_the_movie(self, user, dune):
        _entry(user, "Dune", 2021, movie=dune)

        assert remove_movie(user, dune) == 1
        assert not WatchlistEntry.objects.filter(user=user).exists()

    def test_removes_entry_matched_by_title_and_year(self, user, dune):
        _entry(user, "DUNE", 2021, movie=None)

        assert remove_movie(user, dune) == 1

    def test_removes_every_matching_entry(self, user, dune):
        _entry(user, "Dune (alt spelling)", 2021, movie=dune)
        _entry(user, "Dune", 2021, movie=None)

        assert remove_movie(user, dune) == 2

    def test_returns_zero_when_nothing_matches(self, user, dune):
        assert remove_movie(user, dune) == 0

    def test_keeps_other_films_and_other_users(
        self, user, another_user, dune, alien
    ):
        _entry(user, "Alien", 1979, movie=alien)
        _entry(user, "Dune", 1984, movie=None)
        _entry(another_user, "Dune", 2021, movie=dune)

        assert remove_movie(user, dune) == 0
        assert WatchlistEntry.objects.count() == 3


@pytest.mark.django_db
class TestSavedMovieIds:
    def test_empty_input_returns_empty_set_without_querying(
        self, user, django_assert_num_queries
    ):
        with django_assert_num_queries(0):
            assert saved_movie_ids(user, []) == set()

    def test_returns_ids_of_movies_linked_to_entries(self, user, dune, alien):
        _entry(user, "Dune", 2021, movie=dune)

        assert saved_movie_ids(user, [dune, alien]) == {str(dune.pk)}

    def test_matches_unlinked_entries_by_title_and_year(self, user, dune):
        _entry(user, "Dune", 2021, movie=None)

        assert saved_movie_ids(user, [dune]) == {str(dune.pk)}

    def test_title_match_ignores_case(self, user, dune):
        _entry(user, "dune", 2021, movie=None)

        assert saved_movie_ids(user, [dune]) == {str(dune.pk)}

    def test_same_title_with_other_year_is_not_saved(self, user, dune):
        _entry(user, "Dune", 1984, movie=None)

        assert saved_movie_ids(user, [dune]) == set()

    def test_ignores_other_users_entries(self, user, another_user, dune):
        _entry(another_user, "Dune", 2021, movie=dune)

        assert saved_movie_ids(user, [dune]) == set()

    def test_mixes_linked_and_unlinked_entries(self, user, dune, alien):
        _entry(user, "Dune", 2021, movie=dune)
        _entry(user, "Alien", 1979, movie=None)

        assert saved_movie_ids(user, [dune, alien]) == {
            str(dune.pk),
            str(alien.pk),
        }

    def test_uses_a_single_query(
        self, user, dune, alien, django_assert_num_queries
    ):
        _entry(user, "Dune", 2021, movie=dune)

        with django_assert_num_queries(1):
            saved_movie_ids(user, [dune, alien])


class TestRowsToCsv:
    def test_empty_rows_return_only_the_header(self):
        assert rows_to_csv([]) == ("Title,Year\r\n", 0)

    def test_writes_rows_and_counts_them(self):
        content, count = rows_to_csv([("Dune", 2021), ("Alien", 1979)])

        assert content == "Title,Year\r\nDune,2021\r\nAlien,1979\r\n"
        assert count == 2

    @pytest.mark.parametrize("year", [None, 0])
    def test_missing_year_is_left_blank(self, year):
        content, count = rows_to_csv([("Untitled", year)])

        assert content == "Title,Year\r\nUntitled,\r\n"
        assert count == 1

    def test_quotes_titles_with_commas_and_quotes(self):
        content, _ = rows_to_csv([('Dune, "Part Two"', 2024)])

        assert content == 'Title,Year\r\n"Dune, ""Part Two""",2024\r\n'

    def test_accepts_generators(self):
        rows = ((title, 2000) for title in ("A", "B", "C"))

        content, count = rows_to_csv(rows)

        assert count == 3
        assert content.splitlines() == ["Title,Year", "A,2000", "B,2000", "C,2000"]

    def test_keeps_unicode_titles(self):
        content, _ = rows_to_csv([("Amélie", 2001)])

        assert "Amélie,2001" in content
