from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Mapping

from django.db import transaction

from apps.library.models import Rating, WatchlistEntry, WatchlistSource
from apps.imports.dtos.extraction_result import ExtractionResult
from apps.imports.dtos.import_summary import MovieMatchSummary
from apps.imports.constants import DIARY_CSV, LIKED_CSV, RATINGS_CSV, WATCHED_CSV, WATCHLIST_CSV
from apps.movies.exceptions import MovieMatchNotFound, TMDbError
from apps.movies.models import Movie
from apps.movies.services.movie_cache import (
    fetch_and_store_movies,
    find_cached_movie,
    find_cached_movie_by_tmdb_id,
)
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.services.tmdb_matching import match_movie

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _RatingEntry:
    title: str
    year: int
    rating: float | None = None
    watched_date: date | None = None
    liked: bool = False

FilmKey = tuple[str, int]


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_rating(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _film_key(row: Mapping[str, str]) -> FilmKey | None:
    title = (row.get("Name") or "").strip()
    year = _parse_year(row.get("Year"))
    if not title or year is None:
        return None

    return title, year


def _merge_rating_sources(csvs: Mapping[str, list]) -> dict[FilmKey, _RatingEntry]:
    entries: dict[FilmKey, _RatingEntry] = {}

    def get_or_create(key: FilmKey) -> _RatingEntry:
        if key not in entries:
            entries[key] = _RatingEntry(title=key[0], year=key[1])

        return entries[key]

    for row in csvs.get(WATCHED_CSV, []):
        key = _film_key(row)
        if key:
            get_or_create(key)

    for row in csvs.get(RATINGS_CSV, []):
        key = _film_key(row)
        if not key:
            continue
        rating = _parse_rating(row.get("Rating"))
        if rating is not None:
            get_or_create(key).rating = rating

    diary_by_key: dict[FilmKey, list[Mapping[str, str]]] = defaultdict(list)
    for row in csvs.get(DIARY_CSV, []):
        key = _film_key(row)
        if key:
            diary_by_key[key].append(row)

    for key, rows in diary_by_key.items():
        latest = max(rows, key=lambda r: _parse_date(r.get("Watched Date")) or date.min)
        entry = get_or_create(key)
        watched_date = _parse_date(latest.get("Watched Date"))
        rating = _parse_rating(latest.get("Rating"))
        if watched_date is not None:
            entry.watched_date = watched_date
        if rating is not None:
            entry.rating = rating

    for row in csvs.get(LIKED_CSV, []):
        key = _film_key(row)
        if key:
            get_or_create(key).liked = True

    return entries


def _match_films(
    client: TMDbClient, film_keys: set[FilmKey]
) -> tuple[dict[FilmKey, Movie], MovieMatchSummary]:
    matches: dict[FilmKey, Movie] = {}
    summary = MovieMatchSummary()
    pending_tmdb_id_by_key: dict[FilmKey, int] = {}

    for title, year in sorted(film_keys):
        if summary.tmdb_error is not None:
            summary.unmatched.append(f"{title} ({year})")
            continue

        cached = find_cached_movie(title, year)
        if cached is not None:
            matches[(title, year)] = cached
            summary.matched += 1
            continue

        try:
            match = match_movie(client, title, year)
        except MovieMatchNotFound:
            summary.unmatched.append(f"{title} ({year})")
            continue
        except TMDbError as exc:
            logger.warning(
                "Stopping TMDb matching for this import after a systemic "
                "failure: %s",
                exc,
            )
            summary.tmdb_error = str(exc)
            summary.unmatched.append(f"{title} ({year})")
            continue

        cached_by_tmdb_id = find_cached_movie_by_tmdb_id(match.tmdb_id)
        if cached_by_tmdb_id is not None:
            matches[(title, year)] = cached_by_tmdb_id
            summary.matched += 1
            continue

        pending_tmdb_id_by_key[(title, year)] = match.tmdb_id

    if pending_tmdb_id_by_key:
        movies_by_tmdb_id = fetch_and_store_movies(set(pending_tmdb_id_by_key.values()))
        for key, tmdb_id in pending_tmdb_id_by_key.items():
            movie = movies_by_tmdb_id.get(tmdb_id)
            if movie is not None:
                matches[key] = movie
                summary.matched += 1
            else:
                title, year = key
                summary.without_metadata.append(f"{title} ({year})")

    return matches, summary


def persist_ratings(
    user, csvs: Mapping[str, list], movie_matches: Mapping[FilmKey, Movie]
) -> int:
    merged = _merge_rating_sources(csvs)
    for (title, year), entry in merged.items():
        Rating.objects.update_or_create(
            user=user,
            title=title,
            release_year=year,
            defaults={
                "rating": entry.rating,
                "watched_date": entry.watched_date,
                "liked": entry.liked,
                "movie": movie_matches.get((title, year)),
            },
        )

    return len(merged)


def persist_watchlist(
    user, rows: list, movie_matches: Mapping[FilmKey, Movie]
) -> int:
    count = 0
    for row in rows:
        key = _film_key(row)
        if not key:
            continue
        title, year = key
        WatchlistEntry.objects.update_or_create(
            user=user,
            title=title,
            release_year=year,
            defaults={
                "added_date": _parse_date(row.get("Date")),
                "source": WatchlistSource.IMPORTED,
                "movie": movie_matches.get(key),
            },
        )
        count += 1

    return count


def _collect_film_keys(csvs: Mapping[str, list]) -> set[FilmKey]:
    keys: set[FilmKey] = set(_merge_rating_sources(csvs).keys())
    for row in csvs.get(WATCHLIST_CSV, []):
        key = _film_key(row)
        if key:
            keys.add(key)
    return keys


@transaction.atomic
def persist_letterboxd_records(user, result: ExtractionResult
) -> tuple[dict[str, int], MovieMatchSummary]:
    client = TMDbClient()

    film_keys = _collect_film_keys(result.csvs)
    movie_matches, movie_summary = _match_films(client, film_keys)

    persisted: dict[str, int] = {
        "ratings": persist_ratings(user, result.csvs, movie_matches)
    }
    if WATCHLIST_CSV in result.csvs:
        persisted["watchlist"] = persist_watchlist(
            user, result.csvs[WATCHLIST_CSV], movie_matches
        )

    return persisted, movie_summary
