from __future__ import annotations

from typing import Optional

from django.conf import settings
from pgvector.django import CosineDistance

from apps.movies.models import Movie

DEFAULT_PROPAGATION_K = 10


def propagate_cf_score(
    movie: Movie,
    cf_scores_by_movie_id: dict[int, float],
    k: Optional[int] = DEFAULT_PROPAGATION_K,
) -> Optional[float]:
    if movie.embedding is None or not cf_scores_by_movie_id:
        return None

    neighbors = (
        Movie.objects.filter(id__in=cf_scores_by_movie_id.keys(), embedding__isnull=False)
        .annotate(distance=CosineDistance("embedding", movie.embedding))
        .order_by("distance")[:k]
    )

    numerator = denominator = 0.0
    for neighbor in neighbors:
        similarity = 1 - neighbor.distance
        if similarity <= 0:
            continue
        numerator += similarity * cf_scores_by_movie_id[neighbor.id]
        denominator += similarity

    return (numerator / denominator) if denominator else None
