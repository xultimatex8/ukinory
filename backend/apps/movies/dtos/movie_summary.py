from dataclasses import dataclass

from apps.movies.models import Movie


@dataclass(slots=True)
class MovieCacheSummary:
    stored: dict[int, Movie]
    already_stored: int
    without_metadata: int