from __future__ import annotations

from datetime import date

from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie


def rate_movie(
    user,
    movie: Movie,
    rating: float | None = None,
    liked: bool = False,
    watched_date: date | None = None,
    remove_from_watchlist: bool = True,
) -> Rating:
    entry, _ = Rating.objects.update_or_create(
        user=user,
        title=movie.title,
        release_year=movie.release_year,
        defaults={
            "rating": rating,
            "liked": liked,
            "watched_date": watched_date,
            "movie": movie,
        },
    )

    if remove_from_watchlist:
        WatchlistEntry.objects.filter(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
        ).delete()

    return entry
