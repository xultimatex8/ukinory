from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MovieMatchSummary:
    matched: int = 0
    unmatched: list[str] = field(default_factory=list)
    without_metadata: list[str] = field(default_factory=list)
    tmdb_error: str | None = None


@dataclass(slots=True)
class ImportSummary:
    imported: dict[str, int]
    missing: list[str]
    movies: MovieMatchSummary