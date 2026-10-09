from __future__ import annotations

import random
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

CALIBRATION_SAMPLE_SIZE = 1000
CALIBRATION_MIN_SAMPLE = 50


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


def _catalog_sample() -> Optional[np.ndarray]:
    pks = list(
        Movie.objects.filter(embedding__isnull=False).values_list("pk", flat=True)
    )
    if len(pks) < CALIBRATION_MIN_SAMPLE:
        return None

    sample_pks = random.sample(pks, min(CALIBRATION_SAMPLE_SIZE, len(pks)))
    vectors = Movie.objects.filter(pk__in=sample_pks).values_list(
        "embedding", flat=True
    )
    matrix = np.array([np.asarray(v, dtype=np.float32) for v in vectors])

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def calibrate_fits(
    pool: list[JointCandidate],
    profiles: Sequence[Optional[np.ndarray]],
) -> list[JointCandidate]:
    if not pool:
        return pool

    sample = _catalog_sample()
    if sample is None:
        return pool

    anchors: list[tuple[float, float]] = []
    for i, p in enumerate(profiles):
        unit = _unit(p) if p is not None else None
        if unit is None:
            return pool
        low = float(np.median(sample @ unit))
        high = max(c.per_user[i] for c in pool)
        anchors.append((low, high))

    def fit(sim: float, anchor: tuple[float, float]) -> float:
        low, high = anchor
        if high - low < 1e-9:
            return 0.0
        return float(np.clip((sim - low) / (high - low), 0.0, 1.0))

    return [
        JointCandidate(
            movie=c.movie,
            score=c.score,
            per_user=[fit(s, a) for s, a in zip(c.per_user, anchors)],
        )
        for c in pool
    ]
