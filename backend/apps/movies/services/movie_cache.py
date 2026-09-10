from __future__ import annotations

from typing import Optional

from django.utils import timezone

from apps.movies.models import Genre, Movie
from apps.movies.services.tmdb_matching import match_movie
from apps.movies.services.tmdb_metadata import fetch_movie_metadata
from apps.movies.tmdb_client import TMDbClient


def get_or_fetch_movie(client: TMDbClient, title: str, year: Optional[int]) -> Movie:
    cached = Movie.objects.filter(title__iexact=title, release_year=year).first()
    if cached is not None:
        return cached

    match = match_movie(client, title, year)

    cached_by_tmdb_id = Movie.objects.filter(tmdb_id=match.tmdb_id).first()
    if cached_by_tmdb_id is not None:
        return cached_by_tmdb_id

    metadata = fetch_movie_metadata(client, match.tmdb_id)
    
    return _store_movie(metadata)


def _store_movie(metadata: dict) -> Movie:
    genre_objs = [
        Genre.objects.get_or_create(tmdb_id=g["tmdb_id"], defaults={"name": g["name"]})[0]
        for g in metadata["genres"]
    ]

    movie, _created = Movie.objects.update_or_create(
        tmdb_id=metadata["tmdb_id"],
        defaults={
            "title": metadata["title"],
            "release_year": metadata["release_year"],
            "synopsis": metadata["synopsis"],
            "poster_url": metadata["poster_url"],
            "vote_average": metadata["vote_average"],
            "runtime": metadata["runtime"],
            "streaming_providers": metadata["streaming_providers"],
            "metadata_fetched_at": timezone.now(),
        },
    )
    movie.genres.set(genre_objs)

    return movie
