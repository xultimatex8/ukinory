from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from django.utils import timezone

from apps.movies.exceptions import EmbeddingError, EmbeddingUnavailableError
from apps.movies.models import Genre, Movie
from apps.movies.services.embedding_client import DEFAULT_SYNC_CHUNK_SIZE, EmbeddingClient
from apps.movies.services.embedding_text import build_embedding_text
from apps.movies.services.wikidata_client import WikidataClient
from apps.movies.services.wikidata_metadata import fetch_movies_metadata
from apps.movies.dtos.movie_summary import MovieCacheSummary

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Prepared:
    tmdb_id: int
    metadata: dict
    text: str
    text_hash: str


def find_cached_movie(title: str, year: Optional[int]) -> Optional[Movie]:
    return Movie.objects.filter(title__iexact=title, release_year=year).first()


def find_cached_movie_by_tmdb_id(tmdb_id: int) -> Optional[Movie]:
    return Movie.objects.filter(tmdb_id=tmdb_id).first()


def fetch_and_store_movies(
    tmdb_ids: Iterable[int], defer_embeddings: bool = False
) -> MovieCacheSummary:
    unique_ids = sorted(set(tmdb_ids))

    if not unique_ids:
        return MovieCacheSummary(stored={}, already_stored=0, without_metadata=0)

    wikidata_client = WikidataClient()

    metadata_by_tmdb_id = fetch_movies_metadata(wikidata_client, unique_ids)

    without_metadata = len(set(unique_ids) - set(metadata_by_tmdb_id))

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

    prepared: list[_Prepared] = []
    already_stored = 0

    existing_by_tmdb_id = Movie.objects.in_bulk(list(filtered_metadata), field_name="tmdb_id")

    for tmdb_id, metadata in filtered_metadata.items():
        text = build_embedding_text(metadata)
        if not text.strip():
            continue
        text_hash = embedding_hash(text)

        if _is_up_to_date(existing_by_tmdb_id.get(tmdb_id), text_hash, defer_embeddings):
            already_stored += 1
            continue

        prepared.append(_Prepared(tmdb_id, metadata, text, text_hash))

    vectors: dict[int, list[float]] = {}
    if prepared and not defer_embeddings:
        vectors = _embed_in_chunks(prepared, EmbeddingClient())

    stored = {}
    for item in prepared:
        stored[item.tmdb_id] = _store_movie(item, vectors.get(item.tmdb_id))

    return MovieCacheSummary(
        stored=stored,
        already_stored=already_stored,
        without_metadata=without_metadata,
    )


def embedding_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_up_to_date(existing: Optional[Movie], text_hash: str, defer: bool) -> bool:
    if existing is None:
        return False
    if existing.embedding_source_hash == text_hash:
        return True
    if defer and existing.embedding_target_hash == text_hash:
        return True
    
    return False


def _embed_in_chunks(
    prepared: list[_Prepared], embedding_client: EmbeddingClient
) -> dict[int, list[float]]:
    vectors: dict[int, list[float]] = {}

    for start in range(0, len(prepared), DEFAULT_SYNC_CHUNK_SIZE):
        chunk = prepared[start : start + DEFAULT_SYNC_CHUNK_SIZE]
        try:
            result = embedding_client.embed_many([p.text for p in chunk])
        except EmbeddingUnavailableError as exc:
            logger.warning(
                "Embedding unavailable (%s); %d movie(s) left for the batch job.",
                exc,
                len(prepared) - start,
            )
            break
        except EmbeddingError as exc:
            logger.warning("Could not embed a chunk of %d movie(s): %s", len(chunk), exc)
            continue

        for item, vector in zip(chunk, result):
            vectors[item.tmdb_id] = vector

    return vectors


def _store_movie(item: _Prepared, vector: Optional[list[float]]) -> Movie:
    metadata = item.metadata

    genre_objs = [
        Genre.objects.get_or_create(
            wikidata_id=g["wikidata_id"], defaults={"name": g["name"]}
        )[0]
        for g in metadata["genres"]
    ]

    defaults = {
        "wikidata_id": metadata["wikidata_id"],
        "title": metadata["title"],
        "release_year": metadata["release_year"],
        "wikidata_description": metadata["wikidata_description"],
        "runtime": metadata["runtime"],
        "original_language": metadata["original_language"],
        "directors": metadata["directors"],
        "metadata_fetched_at": timezone.now(),
        "embedding_target_hash": item.text_hash,
    }

    if vector is not None:
        defaults["embedding"] = vector
        defaults["embedding_source_hash"] = item.text_hash

    movie, _created = Movie.objects.update_or_create(tmdb_id=item.tmdb_id, defaults=defaults)
    movie.genres.set(genre_objs)

    return movie
