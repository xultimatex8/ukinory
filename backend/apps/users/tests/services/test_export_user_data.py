import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.common.enums import WatchlistSource
from apps.legal.models import UserLegalAcceptance
from apps.library.models import Rating, WatchlistEntry
from apps.movies.models import Movie
from apps.users.services.export_user_data import (
    _iso,
    _serialize_legal_acceptance,
    _serialize_rating,
    _serialize_swipe,
    _serialize_swipe_session,
    _serialize_watchlist_entry,
    export_user_data,
)
from django.contrib.auth import get_user_model
from apps.common.enums import LegalDocumentType
from apps.legal.tests.factories import make_document


@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

@pytest.fixture
def published_documents(db):
    return SimpleNamespace(
        terms_v1=make_document(LegalDocumentType.TERMS, "1", days_ago=30),
        terms_v2=make_document(LegalDocumentType.TERMS, "2", days_ago=5),
        privacy_v1=make_document(LegalDocumentType.PRIVACY, "1", days_ago=30),
    )

@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]



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
def test_export_user_data_empty_user(user):
    result = export_user_data(user)

    assert "exported_at" in result

    assert result["account"]["email"] == user.email
    assert result["account"]["username"] == user.username
    assert result["account"]["is_guest"] == user.is_guest
    assert result["account"]["created_at"] == user.created_at.isoformat()
    assert result["account"]["last_active_at"] == (
        user.last_active_at.isoformat()
        if user.last_active_at
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

    sessions = MagicMock()
    sessions.values_list.return_value = [10]

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
        sessions=sessions,
        swipes=swipes,
        ratings=ratings,
        watchlist_entries=watchlist_entries,
        legal_acceptances=legal_acceptances,
    )

    with patch("apps.users.services.export_user_data.SwipeSession") as swipe_session_model:
        swipe_session_model.objects.filter.return_value = [session]

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

    session_ids = MagicMock()
    session_ids.values_list.return_value = [20, 35]

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
        sessions=session_ids,
        swipes=swipes,
        ratings=ratings,
        watchlist_entries=watchlist_entries,
        legal_acceptances=legal_acceptances,
    )

    with patch("apps.users.services.export_user_data.SwipeSession") as swipe_session_model:
        swipe_session_model.objects.filter.return_value = sessions

        result = export_user_data(user)

    assert result["swipe_sessions"][0]["session_reference"] == 1
    assert result["swipe_sessions"][1]["session_reference"] == 2


def test_iso_formats_dates_datetimes_and_none():
    assert _iso(None) is None
    assert _iso(date(2025, 1, 2)) == "2025-01-02"
    assert _iso(datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)) == (
        "2025-01-02T03:04:00+00:00"
    )


def test_serialize_swipe_session_without_created_at_attribute():
    session = SimpleNamespace(type="individual", status="waiting", last_seen_at=None)

    assert _serialize_swipe_session(session, 3)["created_at"] is None


def test_serialize_swipe_with_unknown_session_and_no_movie():
    swipe = SimpleNamespace(
        action="skip",
        candidate=SimpleNamespace(movie=None, session_id=99),
        created_at=None,
    )

    result = _serialize_swipe(swipe, {1: 1})

    assert result["session_reference"] is None
    assert result["movie_title"] is None
    assert result["movie_tmdb_id"] is None


def test_serialize_swipe_without_created_at_attribute():
    swipe = SimpleNamespace(action="skip", candidate=None)

    assert _serialize_swipe(swipe, {})["created_at"] is None


@pytest.mark.django_db
def test_export_user_data_includes_ratings_with_matched_movie_ids(user):
    movie = Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)
    Rating.objects.create(
        user=user, title="Dune", release_year=2021, rating=4.5,
        liked=True, watched_date=date(2025, 1, 2), movie=movie,
    )
    Rating.objects.create(
        user=user, title="Unmatched", release_year=1999,
        rating=None, liked=False,
    )

    ratings = {r["title"]: r for r in export_user_data(user)["ratings"]}

    assert ratings["Dune"] == {
        "title": "Dune",
        "release_year": 2021,
        "rating": 4.5,
        "liked": True,
        "watched_date": "2025-01-02",
        "matched_movie_tmdb_id": 438631,
    }
    assert ratings["Unmatched"]["rating"] is None
    assert ratings["Unmatched"]["matched_movie_tmdb_id"] is None


@pytest.mark.django_db
def test_export_user_data_includes_watchlist_entries(user):
    movie = Movie.objects.create(tmdb_id=348, title="Alien", release_year=1979)
    WatchlistEntry.objects.create(
        user=user, title="Alien", release_year=1979,
        added_date=date(2025, 3, 4), source=WatchlistSource.IMPORTED, movie=movie,
    )

    watchlist = export_user_data(user)["watchlist"]

    assert watchlist == [
        {
            "title": "Alien",
            "release_year": 1979,
            "added_date": "2025-03-04",
            "source": WatchlistSource.IMPORTED,
            "matched_movie_tmdb_id": 348,
        }
    ]


@pytest.mark.django_db
def test_export_user_data_includes_legal_acceptances(user, current_documents):
    for document in current_documents:
        UserLegalAcceptance.objects.create(user=user, document=document)

    acceptances = export_user_data(user)["legal_acceptances"]

    assert {(a["document_type"], a["document_version"]) for a in acceptances} == {
        ("TERMS", "2"),
        ("PRIVACY", "1"),
    }
    assert all(datetime.fromisoformat(a["accepted_at"]) for a in acceptances)


@pytest.mark.django_db
def test_export_user_data_excludes_other_users_data(user, another_user):
    Rating.objects.create(
        user=another_user, title="Dune", release_year=2021, rating=4.0, liked=True
    )
    WatchlistEntry.objects.create(user=another_user, title="Alien", release_year=1979)

    result = export_user_data(user)

    assert result["ratings"] == []
    assert result["watchlist"] == []


@pytest.mark.django_db
def test_export_user_data_flags_guest_accounts(guest_user):
    assert export_user_data(guest_user)["account"]["is_guest"] is True


@pytest.mark.django_db
def test_export_user_data_is_json_serializable(user):
    Rating.objects.create(
        user=user, title="Dune", release_year=2021, rating=4.5,
        liked=True, watched_date=date(2025, 1, 2),
    )
    WatchlistEntry.objects.create(
        user=user, title="Alien", release_year=1979,
        added_date=date(2025, 3, 4),
    )

    json.dumps(export_user_data(user))


@pytest.mark.django_db
def test_export_user_data_stamps_the_export_time(user):
    before = datetime.now(timezone.utc)

    result = export_user_data(user)

    exported_at = datetime.fromisoformat(result["exported_at"])
    assert before <= exported_at <= datetime.now(timezone.utc)
