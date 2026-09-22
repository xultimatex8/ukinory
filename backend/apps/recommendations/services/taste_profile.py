from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from apps.library.models import Rating

logger = logging.getLogger(__name__)

MIN_RATING_TO_COUNT = 0.5
RATING_BASELINE = 2.0
LIKED_BOOST = 1.25


def build_taste_profile(user) -> Optional[np.ndarray]:
    ratings = (
        Rating.objects.filter(
            user=user,
            movie__isnull=False,
            movie__embedding__isnull=False,
            rating__gte=MIN_RATING_TO_COUNT,
        )
        .select_related("movie")
    )

    vectors = []
    weights = []

    for rating in ratings:
        vectors.append(np.array(rating.movie.embedding, dtype=np.float32))

        if rating.liked:
            weight = max(rating.rating - RATING_BASELINE, 0.0) + LIKED_BOOST
        else:
            weight = rating.rating - RATING_BASELINE

        weights.append(weight)

    if not vectors:
        logger.info("User %s has no rated+embedded movies; no taste profile.", user.pk)
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
