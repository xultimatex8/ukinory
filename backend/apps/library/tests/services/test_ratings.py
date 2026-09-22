from __future__ import annotations

from datetime import date

import pytest

from apps.library.models import Rating, WatchlistEntry
from apps.library.services.ratings import rate_movie


@pytest.mark.django_db
class TestRateMovie:
    def test_creates_rating(
        self,
        user,
        movie,
    ):
        result = rate_movie(
            user=user,
            movie=movie,
            rating=4.5,
            liked=True,
            watched_date=date(2026, 9, 20),
        )

        assert isinstance(result, Rating)
        assert result.user == user
        assert result.movie == movie
        assert result.title == movie.title
        assert result.release_year == movie.release_year
        assert result.rating == 4.5
        assert result.liked is True
        assert result.watched_date == date(2026, 9, 20)

        assert Rating.objects.filter(
            user=user,
            movie=movie,
        ).count() == 1

    def test_updates_existing_rating(
        self,
        user,
        movie,
    ):
        existing = Rating.objects.create(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
            movie=movie,
            rating=3.0,
            liked=False,
            watched_date=date(2026, 9, 1),
        )

        result = rate_movie(
            user=user,
            movie=movie,
            rating=5.0,
            liked=True,
            watched_date=date(2026, 9, 20),
        )

        assert result.pk == existing.pk
        assert Rating.objects.filter(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
        ).count() == 1

        existing.refresh_from_db()

        assert existing.rating == 5.0
        assert existing.liked is True
        assert existing.watched_date == date(2026, 9, 20)
        assert existing.movie == movie

    def test_rating_values_can_be_none_or_false(
        self,
        user,
        movie,
    ):
        result = rate_movie(
            user=user,
            movie=movie,
            rating=None,
            liked=False,
            watched_date=None,
        )

        assert result.rating is None
        assert result.liked is False
        assert result.watched_date is None

    def test_removes_movie_from_watchlist_by_default(
        self,
        user,
        movie,
    ):
        watchlist_entry = WatchlistEntry.objects.create(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
        )

        rate_movie(
            user=user,
            movie=movie,
            rating=4.0,
        )

        assert not WatchlistEntry.objects.filter(
            pk=watchlist_entry.pk,
        ).exists()

    def test_keeps_movie_in_watchlist_when_remove_disabled(
        self,
        user,
        movie,
    ):
        watchlist_entry = WatchlistEntry.objects.create(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
        )

        rate_movie(
            user=user,
            movie=movie,
            rating=4.0,
            remove_from_watchlist=False,
        )

        assert WatchlistEntry.objects.filter(
            pk=watchlist_entry.pk,
        ).exists()

    def test_does_not_remove_another_users_watchlist_entry(
        self,
        user,
        another_user,
        movie,
    ):
        watchlist_entry = WatchlistEntry.objects.create(
            user=another_user,
            title=movie.title,
            release_year=movie.release_year,
        )

        rate_movie(
            user=user,
            movie=movie,
            rating=4.0,
        )

        assert WatchlistEntry.objects.filter(
            pk=watchlist_entry.pk,
        ).exists()

    def test_does_not_update_another_users_rating(
        self,
        user,
        another_user,
        movie,
    ):
        other_rating = Rating.objects.create(
            user=another_user,
            title=movie.title,
            release_year=movie.release_year,
            movie=movie,
            rating=2.0,
            liked=False,
        )

        result = rate_movie(
            user=user,
            movie=movie,
            rating=5.0,
            liked=True,
        )

        other_rating.refresh_from_db()

        assert result.user == user
        assert result.pk != other_rating.pk
        assert other_rating.rating == 2.0
        assert other_rating.liked is False

        assert Rating.objects.filter(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
        ).count() == 1
