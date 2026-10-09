from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Optional

from apps.movies.exceptions import TMDbError
from apps.movies.services.tmdb_client import TMDbClient
from apps.common.helpers import extract_year

logger = logging.getLogger(__name__)

POSTER_SIZE = "w500"
CARD_POSTER_SIZE = "w342"

POSTER_MAX_WORKERS = 5
POSTER_TIMEOUT_SECONDS = 5
POSTER_MAX_RETRIES = 1


def fetch_live_display_metadata(client: TMDbClient, tmdb_id: int) -> dict[str, Any]:
    details = client.get(
        f"/movie/{tmdb_id}",
        params={"append_to_response": "watch/providers"},
    )

    providers = (details.get("watch/providers") or {}).get("results") or {}

    return {
        "tmdb_id": details["id"],
        "title": details.get("title") or "",
        "release_year": extract_year(details.get("release_date")),
        "synopsis": details.get("overview") or "",
        "poster_url": _poster_url(details.get("poster_path")),
        "vote_average": details.get("vote_average"),
        "runtime": details.get("runtime"),
        "streaming_providers": providers,
        "genres": [
            {"tmdb_id": g["id"], "name": g["name"]}
            for g in details.get("genres") or []
        ],
    }


def fetch_card_metadata(
    client: TMDbClient, tmdb_id: int, size: str = CARD_POSTER_SIZE
) -> dict[str, Any]:
    """Lightweight lookup of what a movie card shows: title, year, poster, genres."""
    details = client.get(f"/movie/{tmdb_id}")
    return {
        "title": details.get("title") or "",
        "release_year": extract_year(details.get("release_date")),
        "poster_url": _poster_url(details.get("poster_path"), size),
        "genres": [g["name"] for g in details.get("genres") or []],
    }


def fetch_card_metadata_bulk(
    tmdb_ids: Iterable[int],
    size: str = CARD_POSTER_SIZE,
    client: Optional[TMDbClient] = None,
) -> dict[int, dict[str, Any]]:
    ids = set(tmdb_ids)
    if not ids:
        return {}

    if client is None:
        try:
            client = TMDbClient(
                max_retries=POSTER_MAX_RETRIES, timeout=POSTER_TIMEOUT_SECONDS
            )
        except TMDbError:
            logger.warning("TMDb client unavailable; skipping TMDb metadata")
            return {}

    def one(tmdb_id: int) -> tuple[int, Optional[dict[str, Any]]]:
        try:
            return tmdb_id, fetch_card_metadata(client, tmdb_id, size)
        except TMDbError as exc:
            logger.info("No TMDb metadata for tmdb_id=%s: %s", tmdb_id, exc)
            return tmdb_id, None

    with ThreadPoolExecutor(max_workers=POSTER_MAX_WORKERS) as pool:
        return {i: m for i, m in pool.map(one, ids) if m is not None}


def _poster_url(poster_path: Optional[str], size: str = POSTER_SIZE) -> str:
    if not poster_path:
        return ""

    return f"https://image.tmdb.org/t/p/{size}{poster_path}"
