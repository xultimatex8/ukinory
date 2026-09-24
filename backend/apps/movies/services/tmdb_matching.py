from __future__ import annotations

import logging
import re
from typing import Optional

from apps.movies.exceptions import MovieMatchNotFound
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.dtos.movie_match import MovieMatch
from apps.common.helpers import extract_year

logger = logging.getLogger(__name__)

YEAR_TOLERANCE = 1


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def match_movie(client: TMDbClient, title: str, year: Optional[int]) -> MovieMatch:
    results = _search(client, title, year)

    if not results and year is not None:
        results = _search(client, title, None)

    if not results:
        raise MovieMatchNotFound(title, year)

    candidates = [(r, extract_year(r.get("release_date"))) for r in results]

    def year_distance(r_year: Optional[int]) -> int:
        if year is None or r_year is None:
            return 99
        
        return abs(r_year - year)

    in_tolerance = [c for c in candidates if year_distance(c[1]) <= YEAR_TOLERANCE]
    pool = in_tolerance or candidates

    normalized_target = _normalize_title(title)
    exact_title_matches = [
        c for c in pool if _normalize_title(c[0].get("title") or "") == normalized_target
    ]
    final_pool = exact_title_matches or pool

    if not final_pool:
        raise MovieMatchNotFound(title, year)

    final_pool.sort(key=lambda c: c[0].get("popularity") or 0.0, reverse=True)
    best, best_year = final_pool[0]

    is_ambiguous = len(final_pool) > 1
    if is_ambiguous:
        logger.info(
            "Ambiguous TMDb match for '%s' (%s): %d plausible candidate(s), "
            "picked tmdb_id=%s by popularity.",
            title, year, len(final_pool), best.get("id"),
        )

    return MovieMatch(
        tmdb_id=best["id"],
        title=best.get("title") or title,
        release_year=best_year,
        popularity=best.get("popularity") or 0.0,
        is_ambiguous=is_ambiguous,
    )


def _search(client: TMDbClient, title: str, year: Optional[int]) -> list[dict]:
    params: dict = {"query": title, "include_adult": "false"}
    if year is not None:
        params["primary_release_year"] = year
    payload = client.get("/search/movie", params=params)

    return payload.get("results") or []
