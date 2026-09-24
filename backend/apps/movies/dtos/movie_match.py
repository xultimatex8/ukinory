from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class MovieMatch:
    tmdb_id: int
    title: str
    release_year: Optional[int]
    popularity: float
    is_ambiguous: bool = False