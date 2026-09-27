from __future__ import annotations

import datetime
import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie
from apps.recommendations.dtos.candidate import RecommendationCandidate
from apps.recommendations.services.taste_profile import build_taste_profile
from apps.swipe_sessions.models import Swipe
from apps.common.enums import SwipeAction

logger = logging.getLogger(__name__)

DEFAULT_POOL_SIZE = 20

SWIPE_COOLDOWN_DAYS: dict = {
    SwipeAction.SKIP: 90,
}
DEFAULT_SWIPE_COOLDOWN_DAYS = 30


def build_candidate_pool(user, pool_size: Optional[int] = DEFAULT_POOL_SIZE) -> list[RecommendationCandidate]:
    profile = build_taste_profile(user)

    excluded_ids = _excluded_movie_ids(user)

    queryset = Movie.objects.filter(embedding__isnull=False).exclude(id__in=excluded_ids)

    if profile is None:
        logger.info("No taste profile for user %s; falling back to unranked pool.", user.pk)
        movies = list(queryset.order_by("-created_at")[:pool_size])
        return [RecommendationCandidate(movie=m, similarity=0.0) for m in movies]

    ranked = (
        queryset
        .annotate(distance=CosineDistance("embedding", profile.tolist()))
        .order_by("distance")[:pool_size]
    )

    return [
        RecommendationCandidate(movie=m, similarity=1 - m.distance)
        for m in ranked
    ]


def _excluded_movie_ids(user) -> set[int]:
    rated = set(
        Rating.objects.filter(user=user, movie__isnull=False).values_list("movie_id", flat=True)
    )
    watchlisted = set(
        WatchlistEntry.objects.filter(user=user, movie__isnull=False).values_list("movie_id", flat=True)
    )

    return rated | watchlisted | _recently_swiped_movie_ids(user)


def _recently_swiped_movie_ids(user) -> set[int]:
    now = timezone.now()
    excluded: set[int] = set()

    for action, cooldown_days in SWIPE_COOLDOWN_DAYS.items():
        cutoff = now - datetime.timedelta(days=cooldown_days)
        ids = Swipe.objects.filter(
            user=user,
            action=action,
            created_at__gte=cutoff,
            candidate__movie__isnull=False,
        ).values_list("candidate__movie_id", flat=True)
        excluded |= set(ids)

    other_actions = set(SwipeAction) - set(SWIPE_COOLDOWN_DAYS)
    if other_actions:
        cutoff = now - datetime.timedelta(days=DEFAULT_SWIPE_COOLDOWN_DAYS)
        ids = Swipe.objects.filter(
            user=user,
            action__in=other_actions,
            created_at__gte=cutoff,
            candidate__movie__isnull=False,
        ).values_list("candidate__movie_id", flat=True)
        excluded |= set(ids)

    return excluded
