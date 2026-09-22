from __future__ import annotations

import pytest

from apps.library.models import Rating, WatchlistEntry


@pytest.fixture
def rating(user, movie):
    return Rating.objects.create(
        user=user,
        title=movie.title,
        release_year=movie.release_year,
        movie=movie,
        rating=4.5,
        liked=True,
    )


@pytest.fixture
def watchlist_entry(user, movie):
    return WatchlistEntry.objects.create(
        user=user,
        title=movie.title,
        release_year=movie.release_year,
        movie=movie,
    )


@pytest.fixture
def movie(db):
    from apps.movies.models import Movie

    return Movie.objects.create(
        tmdb_id=1001,
        title="Test Movie",
        release_year=2025,
    )
