from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from django.conf import settings

from apps.movies.exceptions import TMDbError
from apps.movies.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 5
DEFAULT_MIN_VOTE_COUNT = 50
DEFAULT_NEW_RELEASE_WINDOW_DAYS = 90
DEFAULT_NEW_RELEASE_MIN_VOTE_COUNT = 5
DEFAULT_START_YEAR = 1900
DEFAULT_PAGES_PER_BUCKET = 1
DEFAULT_DECADE_MIN_VOTE_COUNT = 100
DEFAULT_GENRE_MIN_VOTE_COUNT = 50

TMDB_HARD_PAGE_LIMIT = 500


def discover_popular_tmdb_ids(
    client: TMDbClient,
    max_pages: Optional[int] = None,
    min_vote_count: Optional[int] = None,
) -> list[int]:
    max_pages = _setting_or_default(max_pages, "TMDB_DISCOVER_MAX_PAGES", DEFAULT_MAX_PAGES)
    min_vote_count = _setting_or_default(
        min_vote_count, "TMDB_DISCOVER_MIN_VOTE_COUNT", DEFAULT_MIN_VOTE_COUNT
    )

    logger.info(
        "TMDb popular discover: max_pages=%s, min_vote_count=%s",
        max_pages,
        min_vote_count,
    )

    return _discover_ids(
        client,
        max_pages=max_pages,
        params={
            "sort_by": "popularity.desc",
            "vote_count.gte": min_vote_count,
            "include_adult": "false",
        },
    )


def discover_new_release_tmdb_ids(
    client: TMDbClient,
    max_pages: Optional[int] = None,
    window_days: Optional[int] = None,
    min_vote_count: Optional[int] = None,
    today: Optional[date] = None,
) -> list[int]:
    max_pages = _setting_or_default(max_pages, "TMDB_DISCOVER_MAX_PAGES", DEFAULT_MAX_PAGES)
    window_days = _setting_or_default(
        window_days, "TMDB_DISCOVER_NEW_RELEASE_WINDOW_DAYS", DEFAULT_NEW_RELEASE_WINDOW_DAYS
    )
    min_vote_count = _setting_or_default(
        min_vote_count,
        "TMDB_DISCOVER_NEW_RELEASE_MIN_VOTE_COUNT",
        DEFAULT_NEW_RELEASE_MIN_VOTE_COUNT,
    )
    today = today or date.today()
    since = today - timedelta(days=window_days)

    logger.info(
        "TMDb new release discover: max_pages=%s, window_days=%s, "
        "min_vote_count=%s, since=%s, today=%s",
        max_pages,
        window_days,
        min_vote_count,
        since,
        today,
    )

    return _discover_ids(
        client,
        max_pages=max_pages,
        params={
            "sort_by": "primary_release_date.desc",
            "vote_count.gte": min_vote_count,
            "primary_release_date.gte": since.isoformat(),
            "primary_release_date.lte": today.isoformat(),
            "include_adult": "false",
        },
    )


def discover_by_decade_tmdb_ids(
    client: TMDbClient,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    max_pages_per_decade: Optional[int] = None,
    min_vote_count: Optional[int] = None,
) -> list[int]:
    start_year = start_year or getattr(settings, "TMDB_DISCOVER_START_YEAR", DEFAULT_START_YEAR)
    end_year = end_year or date.today().year
    max_pages_per_decade = _setting_or_default(
        max_pages_per_decade, "TMDB_DISCOVER_PAGES_PER_BUCKET", DEFAULT_PAGES_PER_BUCKET
    )
    min_vote_count = _setting_or_default(
        min_vote_count, "TMDB_DISCOVER_DECADE_MIN_VOTE_COUNT", DEFAULT_DECADE_MIN_VOTE_COUNT
    )

    logger.info(
        "TMDb decade discover: start_year=%s, end_year=%s, "
        "max_pages_per_decade=%s, min_vote_count=%s",
        start_year,
        end_year,
        max_pages_per_decade,
        min_vote_count,
    )

    ids: list[int] = []
    for decade_start, decade_end in _decade_buckets(start_year, end_year):
        try:
            bucket_ids = _discover_ids(
                client,
                max_pages=max_pages_per_decade,
                params={
                    "sort_by": "vote_average.desc",
                    "vote_count.gte": min_vote_count,
                    "primary_release_date.gte": date(decade_start, 1, 1).isoformat(),
                    "primary_release_date.lte": date(decade_end, 12, 31).isoformat(),
                    "include_adult": "false",
                },
            )
        except TMDbError as exc:
            logger.warning(
                "Skipping decade %d-%d after a TMDb error: %s",
                decade_start, decade_end, exc,
            )
            continue

        ids.extend(bucket_ids)

    return ids


def fetch_movie_genre_ids(client: TMDbClient) -> list[int]:
    payload = client.get("/genre/movie/list")
    return [g["id"] for g in payload.get("genres") or [] if "id" in g]


def discover_by_genre_tmdb_ids(
    client: TMDbClient,
    genre_ids: Optional[list[int]] = None,
    max_pages_per_genre: Optional[int] = None,
    min_vote_count: Optional[int] = None,
) -> list[int]:
    genre_ids = genre_ids if genre_ids is not None else fetch_movie_genre_ids(client)
    max_pages_per_genre = _setting_or_default(
        max_pages_per_genre, "TMDB_DISCOVER_PAGES_PER_BUCKET", DEFAULT_PAGES_PER_BUCKET
    )
    min_vote_count = _setting_or_default(
        min_vote_count, "TMDB_DISCOVER_GENRE_MIN_VOTE_COUNT", DEFAULT_GENRE_MIN_VOTE_COUNT
    )

    logger.info(
        "TMDb genre discover: max_pages_per_genre=%s, "
        "min_vote_count=%s",
        max_pages_per_genre,
        min_vote_count,
    )

    ids: list[int] = []
    for genre_id in genre_ids:
        try:
            bucket_ids = _discover_ids(
                client,
                max_pages=max_pages_per_genre,
                params={
                    "sort_by": "popularity.desc",
                    "vote_count.gte": min_vote_count,
                    "with_genres": str(genre_id),
                    "include_adult": "false",
                },
            )
        except TMDbError as exc:
            logger.warning(
                "Skipping genre_id %s after a TMDb error: %s", genre_id, exc
            )
            continue

        ids.extend(bucket_ids)

    return ids


def _decade_buckets(start_year: int, end_year: int) -> list[tuple[int, int]]:
    buckets: list[tuple[int, int]] = []
    decade_start = (start_year // 10) * 10

    while decade_start <= end_year:
        buckets.append((decade_start, min(decade_start + 9, end_year)))
        decade_start += 10

    return buckets


def _discover_ids(client: TMDbClient, max_pages: int, params: dict) -> list[int]:
    ids: list[int] = []
    page = 1
    total_pages: Optional[int] = None
    effective_max_pages = min(max_pages, TMDB_HARD_PAGE_LIMIT)

    while page <= effective_max_pages:
        if total_pages is not None and page > total_pages:
            break

        payload = client.get("/discover/movie", params={**params, "page": page})
        results = payload.get("results") or []
        ids.extend(r["id"] for r in results if "id" in r)

        if not results:
            break

        total_pages = payload.get("total_pages") or page
        page += 1

    return ids


def _setting_or_default(explicit: Optional[int], setting_name: str, default: int) -> int:
    if explicit is not None:
        return explicit

    return getattr(settings, setting_name, default)
