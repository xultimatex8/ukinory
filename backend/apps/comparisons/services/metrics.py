from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np

from apps.comparisons.services.snapshot import RatedFilm, UserLibrary


TOP_N = 5
HIGH_RATING = 4.0
DIVERGENCE_THRESHOLD = 1.5
MAX_RATING_GAP = 4.5
MIN_PAIRS_FOR_STATS = 3
WEIGHT_TASTE = 0.4
WEIGHT_AGREEMENT = 0.4
WEIGHT_OVERLAP = 0.2


@dataclass(slots=True)
class ComparisonMetrics:
    public: dict
    internal: dict


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < MIN_PAIRS_FOR_STATS:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def cosine_similarity(
    a: Optional[np.ndarray], b: Optional[np.ndarray]
) -> Optional[float]:
    if a is None or b is None:
        return None
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return None
    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))


def _favourites_counter(lib: UserLibrary, attr: str) -> Counter:
    counter: Counter = Counter()
    for f in lib.films.values():
        if f.liked or (f.rating is not None and f.rating >= HIGH_RATING):
            counter.update(getattr(f, attr))
    return counter


def _top_shared(lib_a: UserLibrary, lib_b: UserLibrary, attr: str) -> list[str]:
    ca, cb = _favourites_counter(lib_a, attr), _favourites_counter(lib_b, attr)
    shared = ca.keys() & cb.keys()
    return sorted(shared, key=lambda n: (-min(ca[n], cb[n]), n))[:TOP_N]


def _round(value: Optional[float], digits: int = 3) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def compute_metrics(
    lib_a: UserLibrary,
    lib_b: UserLibrary,
    taste_a: Optional[np.ndarray],
    taste_b: Optional[np.ndarray],
) -> ComparisonMetrics:
    uid_a, uid_b = str(lib_a.user_id), str(lib_b.user_id)
    n_a, n_b = len(lib_a.films), len(lib_b.films)
    common = lib_a.films.keys() & lib_b.films.keys()
    n_common = len(common)

    pairs = [
        (lib_a.films[k], lib_b.films[k])
        for k in common
        if lib_a.films[k].rating is not None
        and lib_b.films[k].rating is not None
    ]

    gaps = [abs(fa.rating - fb.rating) for fa, fb in pairs]
    mean_gap = _mean(gaps)
    correlation = _pearson(
        [fa.rating for fa, _ in pairs],
        [fb.rating for _, fb in pairs],
    )

    def entry(fa: RatedFilm, fb: RatedFilm) -> dict:
        return {
            "title": fa.title,
            "release_year": fa.release_year,
            "ratings": {uid_a: fa.rating, uid_b: fb.rating},
        }

    agreements = sorted(
        (p for p in pairs if min(p[0].rating, p[1].rating) >= HIGH_RATING),
        key=lambda p: (
            -min(p[0].rating, p[1].rating),
            abs(p[0].rating - p[1].rating),
            p[0].title,
        ),
    )[:TOP_N]

    divergences = sorted(
        (p for p in pairs if abs(p[0].rating - p[1].rating) >= DIVERGENCE_THRESHOLD),
        key=lambda p: (-abs(p[0].rating - p[1].rating), p[0].title),
    )[:TOP_N]

    smaller = min(n_a, n_b)
    union = n_a + n_b - n_common
    overlap_ratio = n_common / smaller if smaller else None
    jaccard = n_common / union if union else None
    taste_similarity = cosine_similarity(taste_a, taste_b)

    components = []
    if taste_similarity is not None:
        components.append((WEIGHT_TASTE, max(0.0, taste_similarity)))
    if mean_gap is not None and len(pairs) >= MIN_PAIRS_FOR_STATS:
        components.append((WEIGHT_AGREEMENT, 1 - mean_gap / MAX_RATING_GAP))
    if overlap_ratio is not None:
        components.append((WEIGHT_OVERLAP, min(1.0, overlap_ratio * 3)))

    score = None
    if components:
        total_w = sum(w for w, _ in components)
        score = round(100 * sum(w * v for w, v in components) / total_w)

    public = {
        "compatibility_score": score,
        "taste_similarity": _round(taste_similarity),
        "library_sizes": {uid_a: n_a, uid_b: n_b},
        "common_count": n_common,
        "overlap_ratio": _round(overlap_ratio),
        "jaccard": _round(jaccard),
        "mean_rating_gap": _round(mean_gap),
        "rating_correlation": _round(correlation),
        "agreements": [entry(*p) for p in agreements],
        "divergences": [entry(*p) for p in divergences],
    }

    internal = {
        "shared_genres": _top_shared(lib_a, lib_b, "genres"),
        "shared_directors": _top_shared(lib_a, lib_b, "directors"),
    }

    return ComparisonMetrics(public=public, internal=internal)
