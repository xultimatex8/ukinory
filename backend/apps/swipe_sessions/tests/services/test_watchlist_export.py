from __future__ import annotations

import csv
import io

import pytest

from apps.common.enums import SwipeAction
from apps.swipe_sessions.models import Swipe
from apps.swipe_sessions.services.watchlist_export import export_watchlist_csv


@pytest.mark.django_db
def test_exports_only_watchlist_swipes(
    user,
    candidate,
    another_candidate,
):
    Swipe.objects.create(
        user=user,
        candidate=candidate,
        action=SwipeAction.WATCHLIST,
    )
    Swipe.objects.create(
        user=user,
        candidate=another_candidate,
        action=SwipeAction.SKIP,
    )

    result = export_watchlist_csv(user=user)

    assert result.rows_written == 1

    rows = list(csv.reader(io.StringIO(result.csv_content)))

    assert rows[0] == ["Title", "Year"]
    assert rows[1] == [
        candidate.movie.title,
        str(candidate.movie.release_year),
    ]
    assert len(rows) == 2


@pytest.mark.django_db
def test_exports_watchlist_swipes_in_reverse_creation_order(
    user,
    candidate,
    another_candidate,
):
    first_swipe = Swipe.objects.create(
        user=user,
        candidate=candidate,
        action=SwipeAction.WATCHLIST,
    )
    second_swipe = Swipe.objects.create(
        user=user,
        candidate=another_candidate,
        action=SwipeAction.WATCHLIST,
    )

    result = export_watchlist_csv(user=user)

    rows = list(csv.reader(io.StringIO(result.csv_content)))

    assert result.rows_written == 2

    assert rows[1] == [
        another_candidate.movie.title,
        str(another_candidate.movie.release_year),
    ]
    assert rows[2] == [
        candidate.movie.title,
        str(candidate.movie.release_year),
    ]

    assert second_swipe.created_at >= first_swipe.created_at


@pytest.mark.django_db
def test_exports_empty_csv_when_user_has_no_watchlist_swipes(
    user,
):
    result = export_watchlist_csv(user=user)

    assert result.rows_written == 0

    rows = list(csv.reader(io.StringIO(result.csv_content)))

    assert rows == [["Title", "Year"]]


@pytest.mark.django_db
def test_uses_empty_year_when_movie_has_no_release_year(
    user,
    candidate,
):
    candidate.movie.release_year = None
    candidate.movie.save(update_fields=["release_year"])

    Swipe.objects.create(
        user=user,
        candidate=candidate,
        action=SwipeAction.WATCHLIST,
    )

    result = export_watchlist_csv(user=user)

    rows = list(csv.reader(io.StringIO(result.csv_content)))

    assert result.rows_written == 1
    assert rows[0] == ["Title", "Year"]
    assert rows[1] == [candidate.movie.title, ""]


@pytest.mark.django_db
def test_does_not_export_other_users_watchlist_swipes(
    user,
    another_user,
    candidate,
):
    Swipe.objects.create(
        user=another_user,
        candidate=candidate,
        action=SwipeAction.WATCHLIST,
    )

    result = export_watchlist_csv(user=user)

    assert result.rows_written == 0

    rows = list(csv.reader(io.StringIO(result.csv_content)))

    assert rows == [["Title", "Year"]]
