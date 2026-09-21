from __future__ import annotations

import logging
from typing import Literal, Optional

from django.conf import settings

from apps.recommendations.services.collaborative import (
    build_rating_matrix,
    find_similar_users,
    predict_cf_score,
)
from apps.recommendations.services.cf_propagation import propagate_cf_score
from apps.recommendations.services.content_based import build_candidate_pool
from apps.recommendations.dtos.candidate import ScoredCandidate

logger = logging.getLogger(__name__)

Strategy = Literal["content", "collaborative", "hybrid"]
DEFAULT_POOL_SIZE = 20
DEFAULT_STRATEGY: Strategy = "hybrid"
DEFAULT_ALPHA = 0.5

RATING_SCALE_MAX = 5.0


def build_hybrid_pool(
    user,
    pool_size: Optional[int] = None,
    strategy: Optional[Strategy] = None,
    alpha: Optional[float] = None,
) -> list[ScoredCandidate]:
    pool_size = _setting_or_default(
        pool_size, "RECOMMENDATION_DEFAULT_POOL_SIZE", DEFAULT_POOL_SIZE
    )
    strategy = _setting_or_default(
        strategy, "RECOMMENDATION_DEFAULT_STRATEGY", DEFAULT_STRATEGY
    )
    alpha = _setting_or_default(
        alpha, "RECOMMENDATION_DEFAULT_ALPHA", DEFAULT_ALPHA
    )

    content_candidates = build_candidate_pool(user, pool_size=pool_size)

    if strategy == "content":
        return [
            ScoredCandidate(c.movie, c.similarity, None, False, c.similarity)
            for c in content_candidates
        ]

    matrix = build_rating_matrix()
    similar_users = find_similar_users(user.id, matrix)

    direct_cf_scores = {
        movie_id: score
        for movie_id in matrix.by_movie
        if (score := predict_cf_score(movie_id, matrix, similar_users)) is not None
    }

    results = []
    for candidate in content_candidates:
        direct = direct_cf_scores.get(candidate.movie.id)
        propagated = direct is None
        cf_raw = direct if direct is not None else propagate_cf_score(candidate.movie, direct_cf_scores)
        cf_normalized = (cf_raw / RATING_SCALE_MAX) if cf_raw is not None else None

        if strategy == "collaborative":
            final = cf_normalized if cf_normalized is not None else 0.0
        else:
            cf_component = cf_normalized if cf_normalized is not None else candidate.similarity
            final = alpha * candidate.similarity + (1 - alpha) * cf_component

        results.append(
            ScoredCandidate(
                movie=candidate.movie,
                content_score=candidate.similarity,
                cf_score=cf_normalized,
                cf_was_propagated=propagated,
                final_score=final,
            )
        )

    results.sort(key=lambda c: c.final_score, reverse=True)
    return results


def _setting_or_default(explicit, setting_name: str, default):
    if explicit is not None:
        return explicit

    return getattr(settings, setting_name, default)
