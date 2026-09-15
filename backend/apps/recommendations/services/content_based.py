from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from pgvector.django import CosineDistance

from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie
from apps.recommendations.dtos.candidate import RecommendationCandidate
from apps.recommendations.models import Swipe
from apps.recommendations.services.taste_profile import build_taste_profile

logger = logging.getLogger(__name__)

DEFAULT_POOL_SIZE = 20


def build_candidate_pool(user, pool_size: Optional[int] = None) -> list[RecommendationCandidate]:
    pool_size = _setting_or_default(pool_size, "RECOMMENDATION_DEFAULT_POOL_SIZE", DEFAULT_POOL_SIZE)

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
    swiped = set(
        Swipe.objects.filter(user=user).values_list("movie_id", flat=True)
    )
    return rated | watchlisted | swiped


def _setting_or_default(explicit: Optional[int], setting_name: str, default: int) -> int:
    if explicit is not None:
        return explicit

    return getattr(settings, setting_name, default)
