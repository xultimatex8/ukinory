from __future__ import annotations

FilmKey = tuple[str, int | None]


def film_key(title: str, release_year: int | None) -> FilmKey:
    return (title.strip().casefold(), release_year)
