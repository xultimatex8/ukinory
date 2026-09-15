from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from apps.library.models import Rating

logger = logging.getLogger(__name__)

MIN_RATING_TO_COUNT = 0.5


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
        weights.append(rating.rating)

    if not vectors:
        logger.info("User %s has no rated+embedded movies; no taste profile.", user.pk)
        return None

    weights_arr = np.array(weights, dtype=np.float32)
    stacked = np.vstack(vectors)

    profile = np.average(stacked, axis=0, weights=weights_arr)
    return profile
