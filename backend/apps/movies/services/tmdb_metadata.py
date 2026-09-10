from __future__ import annotations

from typing import Any, Optional

from apps.movies.tmdb_client import TMDbClient
from apps.common.helpers import extract_year

POSTER_SIZE = "w500"


def fetch_movie_metadata(client: TMDbClient, tmdb_id: int) -> dict[str, Any]:
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


def _poster_url(poster_path: Optional[str]) -> str:
    if not poster_path:
        return ""
    
    return f"https://image.tmdb.org/t/p/{POSTER_SIZE}{poster_path}"
