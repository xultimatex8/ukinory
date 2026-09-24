from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from apps.movies.models import Movie


@dataclass(slots=True)
class RecommendationCandidate:
    movie: Movie
    similarity: float
    justification: str = ""


@dataclass(slots=True)
class ScoredCandidate:
    movie: Movie
    content_score: float
    cf_score: Optional[float]
    cf_was_propagated: bool
    final_score: float