from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from apps.library.models import Rating

FilmKey = tuple[str, int | None]


def film_key(title: str, release_year: int | None) -> FilmKey:
    return (title.strip().casefold(), release_year)


@dataclass(frozen=True, slots=True)
class RatedFilm:
    title: str
    release_year: int | None
    rating: float | None
    liked: bool
    movie_id: Any = None
    genres: frozenset[str] = frozenset()
    directors: tuple[str, ...] = ()


@dataclass(slots=True)
class UserLibrary:
    user_id: Any
    films: dict[FilmKey, RatedFilm] = field(default_factory=dict)


def load_library(user) -> UserLibrary:
    ratings = (
        Rating.objects.filter(user=user)
        .select_related("movie")
        .prefetch_related("movie__genres")
    )
    films: dict[FilmKey, RatedFilm] = {}

    for r in ratings:
        movie = r.movie
        genres = (
            frozenset(g.name for g in movie.genres.all())
            if movie else frozenset()
        )
        raw_directors = (movie.directors or []) if movie else []
        directors = tuple(d for d in raw_directors if isinstance(d, str))
        films[film_key(r.title, r.release_year)] = RatedFilm(
            title=r.title,
            release_year=r.release_year,
            rating=r.rating,
            liked=r.liked,
            movie_id=r.movie_id,
            genres=genres,
            directors=directors,
        )

    return UserLibrary(user_id=user.pk, films=films)


def compute_inputs_hash(libraries: list[UserLibrary]) -> str:
    digest = hashlib.sha256()

    for lib in sorted(libraries, key=lambda l: str(l.user_id)):
        digest.update(f"#{lib.user_id}".encode())
        for key in sorted(lib.films, key=lambda k: (k[0], k[1] or 0)):
            f = lib.films[key]
            digest.update(
                f"|{f.title}|{f.release_year}|{f.rating}|{int(f.liked)}".encode()
            )

    return digest.hexdigest()
