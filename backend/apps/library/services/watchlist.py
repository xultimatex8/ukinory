from __future__ import annotations

import csv
import io
from functools import reduce
from operator import or_
from typing import Iterable, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.library.models import WatchlistEntry
from apps.library.services.keys import film_key
from apps.movies.models import Movie


def _match_q(movies: list[Movie]) -> Q:
    clauses = [Q(movie_id__in=[m.pk for m in movies])]
    clauses += [
        Q(title__iexact=m.title.strip(), release_year=m.release_year)
        for m in movies
    ]
    return reduce(or_, clauses)


def _matching_entries(user, movies: list[Movie]):
    return WatchlistEntry.objects.filter(user=user).filter(_match_q(movies))


@transaction.atomic
def add_movie(user, movie: Movie, source: str, *, overwrite: bool = False) -> WatchlistEntry:
    values = {
        "movie": movie,
        "source": source,
        "added_date": timezone.localdate(),
    }

    entry = _matching_entries(user, [movie]).first()
    if entry is None:
        entry, _ = WatchlistEntry.objects.update_or_create(
            user=user,
            title=movie.title,
            release_year=movie.release_year,
            defaults=values,
        )
        return entry

    if overwrite:
        for field, value in values.items():
            setattr(entry, field, value)
        entry.save(update_fields=list(values))
    elif entry.movie_id is None:
        entry.movie = movie
        entry.save(update_fields=["movie"])
    return entry


def remove_movie(user, movie: Movie) -> int:
    deleted, _ = _matching_entries(user, [movie]).delete()
    return deleted


def saved_movie_ids(user, movies: list[Movie]) -> set[str]:
    if not movies:
        return set()

    ids = {str(m.pk) for m in movies}
    by_key = {film_key(m.title, m.release_year): str(m.pk) for m in movies}

    rows = _matching_entries(user, movies).values_list(
        "movie_id", "title", "release_year"
    )

    saved: set[str] = set()
    for movie_id, title, year in rows:
        if movie_id is not None and str(movie_id) in ids:
            saved.add(str(movie_id))
            continue
        pk = by_key.get(film_key(title, year))
        if pk is not None:
            saved.add(pk)
    return saved


def rows_to_csv(rows: Iterable[tuple[str, Optional[int]]]) -> tuple[str, int]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Title", "Year"])

    count = 0
    for title, year in rows:
        writer.writerow([title, year or ""])
        count += 1
    return buffer.getvalue(), count
