from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.utils import timezone

from apps.movies.models import Genre, Movie
from apps.movies.services.wikidata_client import WikidataClient
from apps.movies.services.wikidata_metadata import fetch_movies_metadata

logger = logging.getLogger(__name__)


def find_cached_movie(title: str, year: Optional[int]) -> Optional[Movie]:
    return Movie.objects.filter(title__iexact=title, release_year=year).first()


def find_cached_movie_by_tmdb_id(tmdb_id: int) -> Optional[Movie]:
    return Movie.objects.filter(tmdb_id=tmdb_id).first()


def fetch_and_store_movies(tmdb_ids: Iterable[int]) -> dict[int, Movie]:
    unique_ids = sorted(set(tmdb_ids))
    if not unique_ids:
        return {}

    wikidata_client = WikidataClient()
    metadata_by_tmdb_id = fetch_movies_metadata(wikidata_client, unique_ids)

    return {
        tmdb_id: _store_movie(tmdb_id, metadata)
        for tmdb_id, metadata in metadata_by_tmdb_id.items()
    }


def _store_movie(tmdb_id: int, metadata: dict) -> Movie:
    genre_objs = [
        Genre.objects.get_or_create(
            wikidata_id=g["wikidata_id"], defaults={"name": g["name"]}
        )[0]
        for g in metadata["genres"]
    ]

    movie, _created = Movie.objects.update_or_create(
        tmdb_id=tmdb_id,
        defaults={
            "wikidata_id": metadata["wikidata_id"],
            "title": metadata["title"],
            "release_year": metadata["release_year"],
            "wikidata_description": metadata["wikidata_description"],
            "runtime": metadata["runtime"],
            "original_language": metadata["original_language"],
            "directors": metadata["directors"],
            "metadata_fetched_at": timezone.now(),
        },
    )
    movie.genres.set(genre_objs)

    return movie
