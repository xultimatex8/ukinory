from __future__ import annotations

from datetime import datetime
import logging
from dataclasses import dataclass
import time
from typing import Callable, Optional

from apps.movies.exceptions import TMDbError
from apps.movies.services.movie_cache import fetch_and_store_movies
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.services.tmdb_discovery import (
    discover_by_decade_tmdb_ids,
    discover_by_genre_tmdb_ids,
    discover_new_release_tmdb_ids,
    discover_popular_tmdb_ids,
)
from apps.movies.dtos.catalog_summary import CatalogSeedSummary

logger = logging.getLogger(__name__)

PoolFn = Callable[[TMDbClient], list[int]]


def seed_movie_catalog_light(client: Optional[TMDbClient] = None) -> CatalogSeedSummary:
    start = datetime.now()
    logger.info(
        "Starting light movie catalog seed at %s.",
        start.strftime("%H:%M:%S"),
    )

    summary = _seed_from_pools(
        client,
        {
            "popular": discover_popular_tmdb_ids,
            "new_release": discover_new_release_tmdb_ids,
        },
    )

    end = datetime.now()
    logger.info(
        "Finished light movie catalog seed at %s (duration: %s).",
        end.strftime("%H:%M:%S"),
        end - start,
    )

    return summary


def seed_movie_catalog_deep(client: Optional[TMDbClient] = None) -> CatalogSeedSummary:
    start = datetime.now()
    logger.info(
        "Starting deep movie catalog seed at %s.",
        start.strftime("%H:%M:%S"),
    )

    summary = _seed_from_pools(
        client,
        {
            "by_decade": discover_by_decade_tmdb_ids,
            "by_genre": discover_by_genre_tmdb_ids,
        },
    )

    end = datetime.now()
    logger.info(
        "Finished deep movie catalog seed at %s (duration: %s).",
        end.strftime("%H:%M:%S"),
        end - start,
    )

    return summary


def seed_movie_catalog(client: Optional[TMDbClient] = None) -> CatalogSeedSummary:
    start = datetime.now()
    logger.info(
        "Starting full movie catalog seed at %s.",
        start.strftime("%H:%M:%S"),
    )

    summary = _seed_from_pools(
        client,
        {
            "popular": discover_popular_tmdb_ids,
            "new_release": discover_new_release_tmdb_ids,
            "by_decade": discover_by_decade_tmdb_ids,
            "by_genre": discover_by_genre_tmdb_ids,
        },
    )

    end = datetime.now()
    logger.info(
        "Finished full movie catalog seed at %s (duration: %s).",
        end.strftime("%H:%M:%S"),
        end - start,
    )

    return summary


def _seed_from_pools(
    client: Optional[TMDbClient], pool_fns: dict[str, PoolFn]
) -> CatalogSeedSummary:
    client = client or TMDbClient()

    pool_sizes: dict[str, int] = {}
    failed_pools: list[str] = []
    all_tmdb_ids: set[int] = set()
    all_stored: dict[int, object] = {}
    already_stored = 0
    without_metadata = 0

    for name, fn in pool_fns.items():
        try:
            pool_ids = fn(client)
        except TMDbError as exc:
            logger.warning("Skipping pool '%s' after a TMDb error: %s", name, exc)
            failed_pools.append(name)
            pool_sizes[name] = 0
            continue

        pool_sizes[name] = len(pool_ids)
        new_ids = set(pool_ids) - all_tmdb_ids
        all_tmdb_ids.update(new_ids)

        if new_ids:
            result = fetch_and_store_movies(new_ids)

            all_stored.update(result.stored)
            already_stored += result.already_stored
            without_metadata += result.without_metadata

    summary = CatalogSeedSummary(
        discovered=len(all_tmdb_ids),
        stored=len(all_stored),
        already_stored=already_stored,
        without_metadata=without_metadata,
        pool_sizes=pool_sizes,
        failed_pools=failed_pools,
    )

    logger.info(
        "Catalog seeding discovered %d movie(s) from pools %s; "
        "stored %d; already stored %d; "
        "%d had no Wikidata metadata coverage; failed pools: %s.",
        summary.discovered,
        pool_sizes,
        summary.stored,
        summary.already_stored,
        summary.without_metadata,
        failed_pools or "none",
    )

    return summary


def format_seed_summary(summary: CatalogSeedSummary) -> str:
    pools = ", ".join(
        f"{name}={count}" for name, count in summary.pool_sizes.items()
    )

    text = (
        f"Discovered {summary.discovered} candidate(s) [{pools}]; "
        f"stored {summary.stored}; "
        f"already stored {summary.already_stored}; "
        f"{summary.without_metadata} had no Wikidata metadata coverage."
    )

    if summary.failed_pools:
        text += f" Failed pools (skipped): {', '.join(summary.failed_pools)}."

    return text
