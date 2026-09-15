from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from django.conf import settings

from apps.library.models import Rating
from apps.recommendations.dtos.rating_matrix import RatingMatrix

logger = logging.getLogger(__name__)

DEFAULT_MIN_RATERS_FOR_CF = 5
DEFAULT_MIN_COMMON_MOVIES = 3
DEFAULT_MAX_SIMILAR_USERS = 30


def build_rating_matrix() -> RatingMatrix:
    by_user: dict[int, dict[int, float]] = {}
    by_movie: dict[int, dict[int, float]] = {}

    rows = Rating.objects.filter(movie__isnull=False, rating__isnull=False).values(
        "user_id", "movie_id", "rating"
    )

    for row in rows:
        by_user.setdefault(row["user_id"], {})[row["movie_id"]] = row["rating"]
        by_movie.setdefault(row["movie_id"], {})[row["user_id"]] = row["rating"]

    return RatingMatrix(by_user=by_user, by_movie=by_movie)


def _cosine(
    a: dict[int, float],
    b: dict[int, float],
    min_common_movies: Optional[int] = None,
) -> Optional[float]:
    min_common_movies = _setting_or_default(
        min_common_movies, "RECOMMENDATION_MIN_COMMON_MOVIES", DEFAULT_MIN_COMMON_MOVIES
    )

    common = set(a) & set(b)
    if len(common) < min_common_movies:
        return None

    a_vec = np.array([a[k] for k in common])
    b_vec = np.array([b[k] for k in common])
    denom = np.linalg.norm(a_vec) * np.linalg.norm(b_vec)

    return float(np.dot(a_vec, b_vec) / denom) if denom else None


def find_similar_users(
    user_id: int,
    matrix: RatingMatrix,
    max_similar_users: Optional[int] = None,
) -> list[tuple[int, float]]:
    max_similar_users = _setting_or_default(
        max_similar_users, "RECOMMENDATION_MAX_SIMILAR_USERS", DEFAULT_MAX_SIMILAR_USERS
    )

    target = matrix.by_user.get(user_id)
    if not target:
        return []

    similarities = [
        (other_id, sim)
        for other_id, ratings in matrix.by_user.items()
        if other_id != user_id
        for sim in [_cosine(target, ratings)]
        if sim is not None and sim > 0
    ]

    similarities.sort(key=lambda pair: pair[1], reverse=True)
    return similarities[:max_similar_users]


def predict_cf_score(
    movie_id: int,
    matrix: RatingMatrix,
    similar_users: list[tuple[int, float]],
    min_raters_for_cf: Optional[int] = None,
) -> Optional[float]:
    min_raters_for_cf = _setting_or_default(
        min_raters_for_cf, "RECOMMENDATION_MIN_RATERS_FOR_CF", DEFAULT_MIN_RATERS_FOR_CF
    )

    raters = matrix.by_movie.get(movie_id, {})
    if len(raters) < min_raters_for_cf:
        return None

    numerator = denominator = 0.0
    for other_id, sim in similar_users:
        rating = raters.get(other_id)
        if rating is None:
            continue
        numerator += sim * rating
        denominator += abs(sim)

    return (numerator / denominator) if denominator else None


def _setting_or_default(explicit: Optional[int], setting_name: str, default: int) -> int:
    if explicit is not None:
        return explicit

    return getattr(settings, setting_name, default)
