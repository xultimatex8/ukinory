from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MovieMatchSummary:
    matched: int = 0
    ambiguous: int = 0
    unmatched: list[str] = field(default_factory=list)
    tmdb_error: str | None = None


@dataclass(slots=True)
class ImportSummary:
    imported: dict[str, int]
    missing: list[str]
    movies: MovieMatchSummary