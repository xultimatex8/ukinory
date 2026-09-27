from __future__ import annotations

import datetime
import logging
from typing import Literal, Optional

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.recommendations.services.collaborative import (
    build_rating_matrix,
    find_similar_users,
    predict_cf_score,
)
from apps.recommendations.services.cf_propagation import propagate_cf_score
from apps.recommendations.services.content_based import build_candidate_pool
from apps.recommendations.dtos.candidate import ScoredCandidate
from apps.swipe_sessions.models import Swipe
from apps.common.enums import SwipeAction

logger = logging.getLogger(__name__)

Strategy = Literal["content", "collaborative", "hybrid"]
DEFAULT_POOL_SIZE = 20
DEFAULT_STRATEGY: Strategy = "hybrid"
DEFAULT_ALPHA = 0.5

RATING_SCALE_MAX = 5.0

SKIP_PENALTY_COOLDOWN_DAYS = 90
SKIP_PENALTY_FULL_FADE_DAYS = 270
SKIP_PENALTY_MAX = 0.35


def build_hybrid_pool(
    user,
    pool_size: Optional[int] = DEFAULT_POOL_SIZE,
    strategy: Optional[Strategy] = DEFAULT_STRATEGY,
    alpha: Optional[float] = DEFAULT_ALPHA,
) -> list[ScoredCandidate]:
    content_candidates = build_candidate_pool(user, pool_size=pool_size)

    skip_penalties = _skip_penalties(user, {c.movie.id for c in content_candidates})

    if strategy == "content":
        return _sorted(
            [
                ScoredCandidate(
                    c.movie,
                    c.similarity,
                    None,
                    False,
                    c.similarity * skip_penalties.get(c.movie.id, 1.0),
                )
                for c in content_candidates
            ]
        )

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

        final *= skip_penalties.get(candidate.movie.id, 1.0)

        results.append(
            ScoredCandidate(
                movie=candidate.movie,
                content_score=candidate.similarity,
                cf_score=cf_normalized,
                cf_was_propagated=propagated,
                final_score=final,
            )
        )

    return _sorted(results)


def _sorted(results: list[ScoredCandidate]) -> list[ScoredCandidate]:
    results.sort(key=lambda c: c.final_score, reverse=True)
    return results


def _skip_penalties(user, movie_ids: set[int]) -> dict[int, float]:
    if not movie_ids:
        return {}

    now = timezone.now()
    span = SKIP_PENALTY_FULL_FADE_DAYS - SKIP_PENALTY_COOLDOWN_DAYS

    last_skips = (
        Swipe.objects.filter(
            user=user,
            action=SwipeAction.SKIP,
            candidate__movie_id__in=movie_ids,
        )
        .values("candidate__movie_id")
        .annotate(last_skipped_at=Max("created_at"))
    )

    penalties: dict[int, float] = {}
    for row in last_skips:
        days_since = (now - row["last_skipped_at"]).total_seconds() / 86400.0
        progress = min(max((days_since - SKIP_PENALTY_COOLDOWN_DAYS) / span, 0.0), 1.0)
        penalties[row["candidate__movie_id"]] = (1 - SKIP_PENALTY_MAX) + SKIP_PENALTY_MAX * progress

    return penalties
