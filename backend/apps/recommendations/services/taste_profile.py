from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from django.utils import timezone

from apps.library.models import Rating
from apps.swipe_sessions.models import Swipe
from apps.common.enums import SwipeAction

logger = logging.getLogger(__name__)

MIN_RATING_TO_COUNT = 0.5

RATING_BASELINE = 2.5

LIKED_BOOST = 1.5

NEGATIVE_RATING_SCALE = 0.7

SWIPE_WEIGHT_SCALE = 0.6
SWIPE_HALF_LIFE_DAYS = 60.0
SWIPE_ACTION_WEIGHTS = {
    SwipeAction.WATCHLIST: 1.0,
    SwipeAction.SKIP: -0.3,
}


def _recency_weight(created_at, half_life_days: float) -> float:
    age_days = (timezone.now() - created_at).total_seconds() / 86400.0
    return 0.5 ** (age_days / half_life_days)


def _rating_vectors_and_weights(user) -> tuple[list[np.ndarray], list[float]]:
    ratings = (
        Rating.objects.filter(
            user=user,
            movie__isnull=False,
            movie__embedding__isnull=False,
            rating__gte=MIN_RATING_TO_COUNT,
        )
        .select_related("movie")
    )

    vectors, weights = [], []
    for rating in ratings:
        vectors.append(np.array(rating.movie.embedding, dtype=np.float32))

        if rating.liked:
            weight = max(rating.rating - RATING_BASELINE, 0.0) + LIKED_BOOST
        else:
            raw = rating.rating - RATING_BASELINE
            weight = raw if raw >= 0 else raw * NEGATIVE_RATING_SCALE

        weights.append(weight)

    return vectors, weights


def _swipe_vectors_and_weights(user) -> tuple[list[np.ndarray], list[float]]:
    swipes = (
        Swipe.objects.filter(
            user=user,
            action__in=SWIPE_ACTION_WEIGHTS.keys(),
            candidate__movie__isnull=False,
            candidate__movie__embedding__isnull=False,
        )
        .select_related("candidate__movie")
    )

    vectors, weights = [], []
    for swipe in swipes:
        movie = swipe.candidate.movie
        base_weight = SWIPE_ACTION_WEIGHTS[swipe.action]
        decay = _recency_weight(swipe.created_at, SWIPE_HALF_LIFE_DAYS)

        vectors.append(np.array(movie.embedding, dtype=np.float32))
        weights.append(SWIPE_WEIGHT_SCALE * base_weight * decay)

    return vectors, weights


def build_taste_profile(user) -> Optional[np.ndarray]:
    rating_vectors, rating_weights = _rating_vectors_and_weights(user)
    swipe_vectors, swipe_weights = _swipe_vectors_and_weights(user)

    vectors = rating_vectors + swipe_vectors
    weights = rating_weights + swipe_weights

    if not vectors:
        logger.info("User %s has no rated/swiped+embedded movies; no taste profile.", user.pk)
        return None

    weights_arr = np.array(weights, dtype=np.float32)
    stacked = np.vstack(vectors)

    if np.all(weights_arr == 0):
        return None

    positive_mask = weights_arr > 0
    negative_mask = weights_arr < 0

    if positive_mask.any() and negative_mask.any():
        positive_profile = np.average(
            stacked[positive_mask],
            axis=0,
            weights=weights_arr[positive_mask],
        )
        negative_profile = np.average(
            stacked[negative_mask],
            axis=0,
            weights=np.abs(weights_arr[negative_mask]),
        )
        profile = positive_profile - negative_profile
    elif positive_mask.any():
        profile = np.average(
            stacked[positive_mask],
            axis=0,
            weights=weights_arr[positive_mask],
        )
    else:
        profile = -np.average(
            stacked[negative_mask],
            axis=0,
            weights=np.abs(weights_arr[negative_mask]),
        )

    return profile.astype(np.float32)
