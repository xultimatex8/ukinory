from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.users.services.export_user_data import (
    _serialize_legal_acceptance,
    _serialize_rating,
    _serialize_swipe,
    _serialize_swipe_session,
    _serialize_watchlist_entry,
    export_user_data,
)


def test_serialize_swipe_session():
    created_at = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
    last_seen_at = datetime(2026, 9, 23, 11, 0, tzinfo=timezone.utc)

    session = SimpleNamespace(
        type="individual",
        status="active",
        created_at=created_at,
        last_seen_at=last_seen_at,
    )

    result = _serialize_swipe_session(session, 1)

    assert result == {
        "session_reference": 1,
        "type": "individual",
        "status": "active",
        "created_at": created_at.isoformat(),
        "last_seen_at": last_seen_at.isoformat(),
    }


def test_serialize_swipe_session_without_created_at_or_last_seen():
    session = SimpleNamespace(
        type="individual",
        status="waiting",
        created_at=None,
        last_seen_at=None,
    )

    result = _serialize_swipe_session(session, 1)

    assert result == {
        "session_reference": 1,
        "type": "individual",
        "status": "waiting",
        "created_at": None,
        "last_seen_at": None,
    }


def test_serialize_swipe_with_candidate():
    created_at = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)

    movie = SimpleNamespace(
        title="Dune: Part Two",
        tmdb_id=693134,
    )

    candidate = SimpleNamespace(
        movie=movie,
        session_id=42,
    )

    swipe = SimpleNamespace(
        action="watchlist",
        candidate=candidate,
        created_at=created_at,
    )

    result = _serialize_swipe(
        swipe,
        {42: 1},
    )

    assert result == {
        "action": "watchlist",
        "movie_title": "Dune: Part Two",
        "movie_tmdb_id": 693134,
        "session_reference": 1,
        "created_at": created_at.isoformat(),
    }


def test_serialize_swipe_without_candidate():
    swipe = SimpleNamespace(
        action="skip",
        candidate=None,
        created_at=None,
    )

    result = _serialize_swipe(swipe, {})

    assert result == {
        "action": "skip",
        "movie_title": None,
        "movie_tmdb_id": None,
        "session_reference": None,
        "created_at": None,
    }


def test_serialize_rating_with_matched_movie():
    watched_date = datetime(2026, 9, 20, 18, 30, tzinfo=timezone.utc)

    movie = SimpleNamespace(tmdb_id=693134)

    rating = SimpleNamespace(
        title="Dune: Part Two",
        release_year=2024,
        rating=4.5,
        liked=True,
        watched_date=watched_date,
        movie_id=123,
        movie=movie,
    )

    result = _serialize_rating(rating)

    assert result == {
        "title": "Dune: Part Two",
        "release_year": 2024,
        "rating": 4.5,
        "liked": True,
        "watched_date": watched_date.isoformat(),
        "matched_movie_tmdb_id": 693134,
    }


def test_serialize_rating_without_matched_movie():
    rating = SimpleNamespace(
        title="Unknown Movie",
        release_year=2020,
        rating=3,
        liked=False,
        watched_date=None,
        movie_id=None,
        movie=None,
    )

    result = _serialize_rating(rating)

    assert result == {
        "title": "Unknown Movie",
        "release_year": 2020,
        "rating": 3,
        "liked": False,
        "watched_date": None,
        "matched_movie_tmdb_id": None,
    }


def test_serialize_watchlist_entry_with_matched_movie():
    added_date = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)

    movie = SimpleNamespace(tmdb_id=550)

    entry = SimpleNamespace(
        title="Fight Club",
        release_year=1999,
        added_date=added_date,
        source="manual",
        movie_id=456,
        movie=movie,
    )

    result = _serialize_watchlist_entry(entry)

    assert result == {
        "title": "Fight Club",
        "release_year": 1999,
        "added_date": added_date.isoformat(),
        "source": "manual",
        "matched_movie_tmdb_id": 550,
    }


def test_serialize_watchlist_entry_without_matched_movie():
    entry = SimpleNamespace(
        title="Unknown Movie",
        release_year=2020,
        added_date=None,
        source="letterboxd",
        movie_id=None,
        movie=None,
    )

    result = _serialize_watchlist_entry(entry)

    assert result == {
        "title": "Unknown Movie",
        "release_year": 2020,
        "added_date": None,
        "source": "letterboxd",
        "matched_movie_tmdb_id": None,
    }


def test_serialize_legal_acceptance():
    accepted_at = datetime(2026, 9, 22, 15, 30, tzinfo=timezone.utc)

    document = SimpleNamespace(
        type="privacy_policy",
        version="1.0",
    )

    acceptance = SimpleNamespace(
        document=document,
        accepted_at=accepted_at,
    )

    result = _serialize_legal_acceptance(acceptance)

    assert result == {
        "document_type": "privacy_policy",
        "document_version": "1.0",
        "accepted_at": accepted_at.isoformat(),
    }


@pytest.mark.django_db
def test_export_user_data_empty_user(registered_user):
    result = export_user_data(registered_user)

    assert "exported_at" in result

    assert result["account"]["email"] == registered_user.email
    assert result["account"]["username"] == registered_user.username
    assert result["account"]["is_guest"] == registered_user.is_guest
    assert result["account"]["created_at"] == registered_user.created_at.isoformat()
    assert result["account"]["last_active_at"] == (
        registered_user.last_active_at.isoformat()
        if registered_user.last_active_at
        else None
    )

    assert result["ratings"] == []
    assert result["watchlist"] == []
    assert result["swipe_sessions"] == []
    assert result["swipes"] == []
    assert result["legal_acceptances"] == []


@pytest.mark.django_db
def test_export_user_data_serializes_swipe_session_and_swipe():
    session = SimpleNamespace(
        pk=10,
        type="individual",
        status="active",
        created_at=datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 9, 23, 11, 0, tzinfo=timezone.utc),
    )

    movie = SimpleNamespace(
        title="Dune: Part Two",
        tmdb_id=693134,
    )

    candidate = SimpleNamespace(
        movie=movie,
        session_id=10,
    )

    swipe = SimpleNamespace(
        action="watchlist",
        candidate=candidate,
        created_at=datetime(2026, 9, 23, 11, 30, tzinfo=timezone.utc),
    )

    swipe_sessions = MagicMock()
    swipe_sessions.all.return_value = [session]

    swipes = MagicMock()
    swipes.select_related.return_value = [swipe]

    ratings = MagicMock()
    ratings.select_related.return_value.all.return_value = []

    watchlist_entries = MagicMock()
    watchlist_entries.select_related.return_value.all.return_value = []

    legal_acceptances = MagicMock()
    legal_acceptances.select_related.return_value.all.return_value = []

    user = SimpleNamespace(
        email="test@example.com",
        username="testuser",
        is_guest=False,
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        last_active_at=None,
        swipe_sessions=swipe_sessions,
        swipes=swipes,
        ratings=ratings,
        watchlist_entries=watchlist_entries,
        legal_acceptances=legal_acceptances,
    )

    result = export_user_data(user)

    assert result["swipe_sessions"] == [
        {
            "session_reference": 1,
            "type": "individual",
            "status": "active",
            "created_at": session.created_at.isoformat(),
            "last_seen_at": session.last_seen_at.isoformat(),
        }
    ]

    assert result["swipes"] == [
        {
            "action": "watchlist",
            "movie_title": "Dune: Part Two",
            "movie_tmdb_id": 693134,
            "session_reference": 1,
            "created_at": swipe.created_at.isoformat(),
        }
    ]


@pytest.mark.django_db
def test_export_user_data_assigns_sequential_session_references():
    sessions = [
        SimpleNamespace(
            pk=20,
            type="individual",
            status="waiting",
            created_at=None,
            last_seen_at=None,
        ),
        SimpleNamespace(
            pk=35,
            type="individual",
            status="active",
            created_at=None,
            last_seen_at=None,
        ),
    ]

    swipe_sessions = MagicMock()
    swipe_sessions.all.return_value = sessions

    swipes = MagicMock()
    swipes.select_related.return_value.all.return_value = []

    ratings = MagicMock()
    ratings.select_related.return_value.all.return_value = []

    watchlist_entries = MagicMock()
    watchlist_entries.select_related.return_value.all.return_value = []

    legal_acceptances = MagicMock()
    legal_acceptances.select_related.return_value.all.return_value = []

    user = SimpleNamespace(
        email="test@example.com",
        username="testuser",
        is_guest=False,
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        last_active_at=None,
        swipe_sessions=swipe_sessions,
        swipes=swipes,
        ratings=ratings,
        watchlist_entries=watchlist_entries,
        legal_acceptances=legal_acceptances,
    )

    result = export_user_data(user)

    assert result["swipe_sessions"][0]["session_reference"] == 1
    assert result["swipe_sessions"][1]["session_reference"] == 2
