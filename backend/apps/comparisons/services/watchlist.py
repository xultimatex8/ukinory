from __future__ import annotations

import csv
import io

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.enums import WatchlistSource
from apps.comparisons.exceptions import (
    RecommendationNotFoundError,
    RoomNotReadyError,
)
from apps.comparisons.models import ComparisonNarrative, ComparisonSession
from apps.library.models import WatchlistEntry
from apps.movies.models import Movie


def _recommended_movies(room: ComparisonSession) -> list[Movie]:
    comparison = getattr(room, "comparison", None)
    if comparison is None:
        raise RoomNotReadyError

    narrative = ComparisonNarrative.objects.filter(
        comparison=comparison, inputs_hash=comparison.inputs_hash
    ).first()
    if narrative is None:
        raise RoomNotReadyError

    ids = [str(r["movie_id"]) for r in narrative.recommendations]
    by_id = {str(m.pk): m for m in Movie.objects.filter(pk__in=ids)}
    return [by_id[i] for i in ids if i in by_id]


def _get_recommended_movie(room: ComparisonSession, movie_id) -> Movie:
    movie = next(
        (m for m in _recommended_movies(room) if str(m.pk) == str(movie_id)),
        None,
    )
    if movie is None:
        raise RecommendationNotFoundError
    return movie


def _saved_movie_ids(user, movies: list[Movie]) -> set[str]:
    if not movies:
        return set()

    ids = {str(m.pk) for m in movies}
    by_key = {
        (m.title.strip().casefold(), m.release_year): str(m.pk) for m in movies
    }

    rows = (
        WatchlistEntry.objects.filter(user=user)
        .filter(
            Q(movie_id__in=[m.pk for m in movies])
            | Q(title__in=[m.title for m in movies])
        )
        .values_list("movie_id", "title", "release_year")
    )

    saved: set[str] = set()
    for movie_id, title, year in rows:
        if movie_id is not None and str(movie_id) in ids:
            saved.add(str(movie_id))
            continue
        key = (title.strip().casefold(), year)
        if key in by_key:
            saved.add(by_key[key])
    return saved


@transaction.atomic
def add_recommendation_to_watchlist(*, room, user, movie_id) -> None:
    movie = _get_recommended_movie(room, movie_id)

    entry, created = WatchlistEntry.objects.get_or_create(
        user=user,
        title=movie.title,
        release_year=movie.release_year,
        defaults={
            "movie": movie,
            "source": WatchlistSource.COMPARISON_ADDED,
            "added_date": timezone.localdate(),
        },
    )
    if not created and entry.movie_id is None:
        entry.movie = movie
        entry.save(update_fields=["movie"])


@transaction.atomic
def remove_recommendation_from_watchlist(*, room, user, movie_id) -> None:
    movie = _get_recommended_movie(room, movie_id)
    WatchlistEntry.objects.filter(user=user).filter(
        Q(movie=movie)
        | Q(title=movie.title, release_year=movie.release_year)
    ).delete()


def attach_watchlist_state(payload: dict, user) -> dict:
    recs = payload.get("recommendations", [])
    ids = [r["movie_id"] for r in recs]
    movies = list(Movie.objects.filter(pk__in=ids))
    saved = _saved_movie_ids(user, movies)
    return {
        **payload,
        "recommendations": [
            {**r, "in_watchlist": str(r["movie_id"]) in saved} for r in recs
        ],
    }


def export_recommendations_csv(*, room, user) -> tuple[str, int]:
    movies = _recommended_movies(room)
    saved = _saved_movie_ids(user, movies)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Title", "Year"])

    count = 0
    for m in movies:
        if str(m.pk) in saved:
            writer.writerow([m.title, m.release_year or ""])
            count += 1
    return buffer.getvalue(), count
