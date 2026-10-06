from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
from pgvector.django import CosineDistance

from apps.library.models import Rating
from apps.movies.models import Movie
from apps.recommendations.services.taste_profile import build_taste_profile
from apps.recommendations.dtos.candidate import JointCandidate

DEFAULT_POOL_SIZE = 100
LEAST_MISERY_WEIGHT = 0.5


def user_taste_profiles(users: Sequence) -> list[Optional[np.ndarray]]:
    return [build_taste_profile(u) for u in users]


def _unit(v: np.ndarray) -> Optional[np.ndarray]:
    norm = float(np.linalg.norm(v))
    
    return None if norm == 0 else (v / norm).astype(np.float32)


def build_joint_profile(
    profiles: Sequence[Optional[np.ndarray]],
) -> Optional[np.ndarray]:
    units = []
    for p in profiles:
        if p is None:
            return None
        u = _unit(p)
        if u is None:
            return None
        units.append(u)

    return np.mean(units, axis=0).astype(np.float32) if units else None


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_joint_candidates(
    *,
    users: Sequence,
    profiles: Optional[Sequence[Optional[np.ndarray]]] = None,
    limit: int = 10,
    pool_size: int = DEFAULT_POOL_SIZE,
    least_misery_weight: float = LEAST_MISERY_WEIGHT,
) -> list[JointCandidate]:
    profiles = (
        list(profiles)
        if profiles is not None
        else user_taste_profiles(users)
    )

    joint = build_joint_profile(profiles)
    if joint is None:
        return []

    watched = (
        Rating.objects.filter(
            user__in=users,
            movie__isnull=False,
        ).values("movie_id")
    )

    shortlist = list(
        Movie.objects.filter(embedding__isnull=False)
        .exclude(pk__in=watched)
        .annotate(distance=CosineDistance("embedding", joint))
        .order_by("distance")
        .prefetch_related("genres")[:pool_size]
    )

    candidates = []

    for movie in shortlist:
        vec = np.array(movie.embedding, dtype=np.float32)
        sims = [_cos(vec, p) for p in profiles]
        score = (
            (1 - least_misery_weight) * (sum(sims) / len(sims))
            + least_misery_weight * min(sims)
        )
        candidates.append(
            JointCandidate(
                movie=movie,
                score=score,
                per_user=sims,
            )
        )

    candidates.sort(key=lambda c: -c.score)

    return candidates[:limit]
