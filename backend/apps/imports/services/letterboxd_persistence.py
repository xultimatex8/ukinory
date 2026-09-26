from __future__ import annotations

import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Mapping, Optional

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

from apps.swipe_sessions.services.justification import DEFAULT_MAX_HISTORY_MOVIES

logger = logging.getLogger(__name__)

_MATCH_WORKERS = 8


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


def _needs_embedding(movie: Movie) -> bool:
    return movie.embedding is None and movie.embedding_batch_id is None


@dataclass(slots=True)
class _MatchOutcome:
    key: FilmKey
    cached_movie: Optional[Movie] = None
    pending_tmdb_id: Optional[int] = None
    not_found: bool = False
    tmdb_error: Optional[str] = None


def _resolve_one(client: TMDbClient, key: FilmKey) -> _MatchOutcome:
    title, year = key

    cached = find_cached_movie(title, year)
    if cached is not None:
        return _MatchOutcome(key=key, cached_movie=cached)

    try:
        match = match_movie(client, title, year)
    except MovieMatchNotFound:
        return _MatchOutcome(key=key, not_found=True)
    except TMDbError as exc:
        return _MatchOutcome(key=key, tmdb_error=str(exc))

    cached_by_tmdb_id = find_cached_movie_by_tmdb_id(match.tmdb_id)
    if cached_by_tmdb_id is not None:
        return _MatchOutcome(key=key, cached_movie=cached_by_tmdb_id)

    return _MatchOutcome(key=key, pending_tmdb_id=match.tmdb_id)


def _match_films(
    client: TMDbClient,
    film_keys: set[FilmKey],
    priority_keys: set[FilmKey],
) -> tuple[dict[FilmKey, Movie], MovieMatchSummary]:
    t_start = time.perf_counter()
    matches: dict[FilmKey, Movie] = {}
    summary = MovieMatchSummary()
    pending_tmdb_id_by_key: dict[FilmKey, int] = {}
    priority_ids: set[int] = set()

    sorted_keys = sorted(film_keys)
    stop_after_tmdb_error = False

    with ThreadPoolExecutor(max_workers=_MATCH_WORKERS) as pool:
        future_to_key = {
            pool.submit(_resolve_one, client, key): key for key in sorted_keys
        }

        for future in future_to_key:
            key = future_to_key[future]
            title, year = key
            is_priority = key in priority_keys

            if stop_after_tmdb_error:
                summary.unmatched.append(f"{title} ({year})")
                continue

            outcome = future.result()

            if outcome.tmdb_error is not None:
                logger.warning(
                    "Stopping TMDb matching for this import after a systemic "
                    "failure: %s",
                    outcome.tmdb_error,
                )
                summary.tmdb_error = outcome.tmdb_error
                summary.unmatched.append(f"{title} ({year})")
                stop_after_tmdb_error = True
                continue

            if outcome.not_found:
                summary.unmatched.append(f"{title} ({year})")
                continue

            if outcome.cached_movie is not None:
                matches[key] = outcome.cached_movie
                summary.matched += 1
                if is_priority and _needs_embedding(outcome.cached_movie):
                    priority_ids.add(outcome.cached_movie.tmdb_id)
                continue

            pending_tmdb_id_by_key[key] = outcome.pending_tmdb_id
            if is_priority:
                priority_ids.add(outcome.pending_tmdb_id)

    t_matched = time.perf_counter()
    logger.info(
        "_match_films: matching phase for %d film(s) took %.2fs "
        "(%d matched so far, %d pending tmdb ids, %d priority)",
        len(sorted_keys), t_matched - t_start,
        summary.matched, len(pending_tmdb_id_by_key), len(priority_ids),
    )

    other_ids = set(pending_tmdb_id_by_key.values()) - priority_ids
    stored: dict[int, Movie] = {}

    if priority_ids:
        stored.update(fetch_and_store_movies(priority_ids).stored)
    t_priority = time.perf_counter()
    if priority_ids:
        logger.info(
            "_match_films: fetch_and_store_movies(priority=%d) took %.2fs",
            len(priority_ids), t_priority - t_matched,
        )

    if other_ids:
        stored.update(
            fetch_and_store_movies(other_ids, defer_embeddings=True).stored
        )
    t_other = time.perf_counter()
    if other_ids:
        logger.info(
            "_match_films: fetch_and_store_movies(deferred=%d) took %.2fs",
            len(other_ids), t_other - t_priority,
        )

    for key, tmdb_id in pending_tmdb_id_by_key.items():
        movie = stored.get(tmdb_id)
        if movie is not None:
            matches[key] = movie
            summary.matched += 1
        else:
            title, year = key
            summary.without_metadata.append(f"{title} ({year})")

    logger.info(
        "_match_films: total %.2fs for %d film(s) "
        "(matched=%d unmatched=%d without_metadata=%d)",
        time.perf_counter() - t_start, len(sorted_keys),
        summary.matched, len(summary.unmatched), len(summary.without_metadata),
    )

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


def persist_letterboxd_records(
    user, result: ExtractionResult
) -> tuple[dict[str, int], MovieMatchSummary]:
    client = TMDbClient()

    film_keys = _collect_film_keys(result.csvs)
    merged = _merge_rating_sources(result.csvs)
    rated = sorted(
        (k for k, e in merged.items() if e.rating is not None),
        key=lambda k: (merged[k].liked, merged[k].rating),
        reverse=True,
    )
    priority_keys = set(rated[: DEFAULT_MAX_HISTORY_MOVIES])

    movie_matches, movie_summary = _match_films(client, film_keys, priority_keys)

    with transaction.atomic():
        persisted: dict[str, int] = {
            "ratings": persist_ratings(user, result.csvs, movie_matches)
        }
        if WATCHLIST_CSV in result.csvs:
            persisted["watchlist"] = persist_watchlist(
                user, result.csvs[WATCHLIST_CSV], movie_matches
            )

    return persisted, movie_summary