from __future__ import annotations

from apps.common.enums import WatchlistSource
from apps.common.exceptions import SessionNotReadyError
from apps.comparisons.exceptions import RecommendationNotFoundError
from apps.comparisons.models import ComparisonNarrative, ComparisonSession
from apps.library.services.watchlist import (
    add_movie,
    remove_movie,
    rows_to_csv,
    saved_movie_ids,
)
from apps.movies.models import Movie


def _recommended_movies(room: ComparisonSession) -> list[Movie]:
    comparison = getattr(room, "comparison", None)
    if comparison is None:
        raise SessionNotReadyError

    narrative = ComparisonNarrative.objects.filter(
        comparison=comparison, inputs_hash=comparison.inputs_hash
    ).first()
    if narrative is None:
        raise SessionNotReadyError

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


def add_recommendation_to_watchlist(*, room, user, movie_id) -> None:
    movie = _get_recommended_movie(room, movie_id)
    add_movie(user, movie, WatchlistSource.COMPARISON_ADDED)


def remove_recommendation_from_watchlist(*, room, user, movie_id) -> None:
    movie = _get_recommended_movie(room, movie_id)
    remove_movie(user, movie)


def attach_watchlist_state(payload: dict, user) -> dict:
    recs = payload.get("recommendations", [])
    ids = [r["movie_id"] for r in recs]
    movies = list(Movie.objects.filter(pk__in=ids))
    saved = saved_movie_ids(user, movies)
    return {
        **payload,
        "recommendations": [
            {**r, "in_watchlist": str(r["movie_id"]) in saved} for r in recs
        ],
    }


def export_recommendations_csv(*, room, user) -> tuple[str, int]:
    movies = _recommended_movies(room)
    saved = saved_movie_ids(user, movies)
    return rows_to_csv(
        (m.title, m.release_year) for m in movies if str(m.pk) in saved
    )
