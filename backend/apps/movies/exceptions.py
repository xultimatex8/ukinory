from __future__ import annotations

from typing import Optional


class TMDbError(Exception):
    """Base class for anything that goes wrong talking to TMDb."""


class TMDbNotFoundError(TMDbError):
    """TMDb returned 404 for a resource expected to exist."""


class TMDbRateLimitedError(TMDbError):
    """TMDb kept returning 429 even after exhausting retry budget."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"TMDb rate limit exceeded; it asked us to wait {retry_after:.1f}s "
            "and retries were exhausted before that."
        )


class TMDbUnavailableError(TMDbError):
    """Network failure or persistent 5xx from TMDb after retries."""


class MovieMatchError(Exception):
    """Base class for per-title matching problems. One bad title shouldn't fail 
    the whole import, it should just be reported as unmatched."""

    def __init__(self, title: str, year: Optional[int], message: str):
        self.title = title
        self.year = year
        super().__init__(message)


class MovieMatchNotFound(MovieMatchError):
    def __init__(self, title: str, year: Optional[int]):
        super().__init__(
            title,
            year,
            f"No plausible TMDb match for '{title}' ({year or 'unknown year'}).",
        )

class WikidataError(Exception):
    """Base error for Wikidata client/metadata failures."""


class WikidataNotFoundError(WikidataError):
    """Raised when no Wikidata item covers a given resource/tmdb_id."""


class WikidataUnavailableError(WikidataError):
    """Raised after retries are exhausted on transient failures."""
