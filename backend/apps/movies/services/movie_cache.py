from __future__ import annotations

import hashlib
import logging
from typing import Iterable, Optional

from django.utils import timezone

from apps.movies.exceptions import EmbeddingError
from apps.movies.models import Genre, Movie
from apps.movies.services.embedding_client import EmbeddingClient
from apps.movies.services.embedding_text import build_embedding_text
from apps.movies.services.wikidata_client import WikidataClient
from apps.movies.services.wikidata_metadata import fetch_movies_metadata
from apps.movies.dtos.movie_summary import MovieCacheSummary

logger = logging.getLogger(__name__)


def find_cached_movie(title: str, year: Optional[int]) -> Optional[Movie]:
    return Movie.objects.filter(title__iexact=title, release_year=year).first()


def find_cached_movie_by_tmdb_id(tmdb_id: int) -> Optional[Movie]:
    return Movie.objects.filter(tmdb_id=tmdb_id).first()


def fetch_and_store_movies(tmdb_ids: Iterable[int]) -> MovieCacheSummary:
    unique_ids = sorted(set(tmdb_ids))

    if not unique_ids:
        return MovieCacheSummary(
            stored={},
            already_stored=0,
            without_metadata=0,
        )

    wikidata_client = WikidataClient()
    embedding_client = EmbeddingClient()

    metadata_by_tmdb_id = fetch_movies_metadata(
        wikidata_client,
        unique_ids,
    )

    without_metadata = len(
        set(unique_ids) - set(metadata_by_tmdb_id)
    )

    filtered_metadata = {}
    used_wikidata_ids = set()

    for tmdb_id, metadata in metadata_by_tmdb_id.items():
        wikidata_id = metadata["wikidata_id"]

        if wikidata_id in used_wikidata_ids:
            logger.warning(
                "Skipping TMDb ID %s: Wikidata ID %s is already "
                "associated with another TMDb ID in this batch.",
                tmdb_id,
                wikidata_id,
            )
            continue

        used_wikidata_ids.add(wikidata_id)
        filtered_metadata[tmdb_id] = metadata

    stored = {}
    already_stored = 0

    for tmdb_id, metadata in filtered_metadata.items():
        movie = _store_movie(
            tmdb_id,
            metadata,
            embedding_client,
        )

        if movie is not None:
            stored[tmdb_id] = movie
        else:
            already_stored += 1

    return MovieCacheSummary(
        stored=stored,
        already_stored=already_stored,
        without_metadata=without_metadata,
    )


def _embedding_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _store_movie(tmdb_id: int, metadata: dict, embedding_client: EmbeddingClient) -> Optional[Movie]:
    genre_objs = [
        Genre.objects.get_or_create(
            wikidata_id=g["wikidata_id"], defaults={"name": g["name"]}
        )[0]
        for g in metadata["genres"]
    ]

    embedding_text = build_embedding_text(metadata)
    new_hash = _embedding_hash(embedding_text)

    existing = Movie.objects.filter(tmdb_id=tmdb_id).first()
    needs_embedding = existing is None or existing.embedding_source_hash != new_hash

    defaults = {
        "wikidata_id": metadata["wikidata_id"],
        "title": metadata["title"],
        "release_year": metadata["release_year"],
        "wikidata_description": metadata["wikidata_description"],
        "runtime": metadata["runtime"],
        "original_language": metadata["original_language"],
        "directors": metadata["directors"],
        "metadata_fetched_at": timezone.now(),
    }

    if needs_embedding:
        try:
            defaults["embedding"] = embedding_client.embed(embedding_text)
            defaults["embedding_source_hash"] = new_hash
        except EmbeddingError as exc:
            logger.warning(
                "Could not generate embedding for TMDb ID %s: %s", tmdb_id, exc
            )

    if existing is not None and not needs_embedding:
        return None

    movie, _created = Movie.objects.update_or_create(tmdb_id=tmdb_id, defaults=defaults)
    movie.genres.set(genre_objs)

    return movie
