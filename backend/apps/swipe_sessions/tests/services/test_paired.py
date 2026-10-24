from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.common.enums import (
    InviteStatus,
    InviteType,
    SessionStatus,
    SessionType,
    SwipeAction,
    SwipeSessionType,
)
from apps.invites.exceptions import TooManyPendingInvitesError
from apps.invites.models import Invite
from apps.swipe_sessions.exceptions import PairedSessionRequiredError
from apps.swipe_sessions.models import Swipe, SwipeSession, SwipeSessionCandidate
from apps.swipe_sessions.services.paired import (
    build_paired_state,
    create_paired_session,
    match_payload,
    matched_candidates,
    regenerate_paired_invite,
    require_paired,
)
from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)

@pytest.fixture
def another_movie(db):
    return Movie.objects.create(tmdb_id=348, title="Alien", release_year=1979)

@pytest.fixture
def swipe_session(db):
    return SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )


MODULE = "apps.swipe_sessions.services.paired"


def make_paired_session(*users, status=SessionStatus.ACTIVE):
    session = SwipeSession.objects.create(
        type=SwipeSessionType.PAIRED,
        session_type=SessionType.SWIPE_SESSION,
        status=status,
    )
    session.users.add(*users)
    return session


def add_candidate(session, movie, position):
    return SwipeSessionCandidate.objects.create(
        session=session, movie=movie, score=0.5, position=position
    )


def swipe(user, candidate, action, *, when=None):
    row = Swipe.objects.create(user=user, candidate=candidate, action=action)
    if when is not None:
        Swipe.objects.filter(pk=row.pk).update(created_at=when)
    return row


class TestRequirePaired:
    def test_a_paired_session_passes(self):
        require_paired(SimpleNamespace(type=SwipeSessionType.PAIRED))

    def test_any_other_session_is_rejected(self):
        with pytest.raises(PairedSessionRequiredError):
            require_paired(SimpleNamespace(type="solo"))


class TestMatchPayload:
    def test_identifiers_are_strings_and_the_movie_is_described(self):
        candidate = SimpleNamespace(
            pk=5,
            movie=SimpleNamespace(
                pk=7, tmdb_id=438631, title="Dune", release_year=2021
            ),
        )

        assert match_payload(candidate) == {
            "candidate_id": "5",
            "movie_id": "7",
            "tmdb_id": 438631,
            "title": "Dune",
            "release_year": 2021,
        }

    def test_an_unknown_release_year_stays_none(self):
        candidate = SimpleNamespace(
            pk=1, movie=SimpleNamespace(pk=2, tmdb_id=3, title="X", release_year=None)
        )

        assert match_payload(candidate)["release_year"] is None


@pytest.mark.django_db
class TestCreatePairedSession:
    def test_creates_a_waiting_paired_session_for_the_user(self, user):
        session, _ = create_paired_session(user)

        assert session.type == SwipeSessionType.PAIRED
        assert session.status == SessionStatus.WAITING
        assert list(session.users.all()) == [user]

    def test_creates_a_pending_paired_swipe_invite_for_that_session(self, user):
        session, invite = create_paired_session(user)

        assert invite.inviter == user
        assert invite.type == InviteType.PAIRED_SWIPE
        assert invite.status == InviteStatus.PENDING
        assert invite.session_id == session.pk

    def test_the_session_is_marked_as_seen(self, user):
        with patch(f"{MODULE}.touch_session") as touch:
            session, _ = create_paired_session(user)

        touch.assert_called_once_with(session.pk)

    def test_nothing_is_created_when_the_invite_cannot_be_created(self, user):
        with patch(f"{MODULE}.create_invite", side_effect=TooManyPendingInvitesError):
            with pytest.raises(TooManyPendingInvitesError):
                create_paired_session(user)

        assert not SwipeSession.objects.exists()


@pytest.mark.django_db
class TestRegeneratePairedInvite:
    def test_only_paired_sessions_can_regenerate_invites(self, user, swipe_session):
        with patch(f"{MODULE}.regenerate_session_invite") as regenerate:
            with pytest.raises(PairedSessionRequiredError):
                regenerate_paired_invite(user=user, session=swipe_session)

        regenerate.assert_not_called()

    def test_delegates_to_the_generic_regeneration(self, user):
        session = make_paired_session(user, status=SessionStatus.WAITING)

        with patch(f"{MODULE}.regenerate_session_invite") as regenerate:
            result = regenerate_paired_invite(user=user, session=session)

        regenerate.assert_called_once_with(
            user=user, session=session, invite_type=InviteType.PAIRED_SWIPE
        )
        assert result is regenerate.return_value

    def test_the_previous_invite_is_replaced_by_a_new_one(self, user):
        session, old = create_paired_session(user)

        new = regenerate_paired_invite(user=user, session=session)

        old.refresh_from_db()
        assert old.status == InviteStatus.EXPIRED
        assert new.status == InviteStatus.PENDING
        assert new.type == InviteType.PAIRED_SWIPE
        assert Invite.objects.filter(
            session_id=session.pk, status=InviteStatus.PENDING
        ).count() == 1


@pytest.mark.django_db
class TestMatchedCandidates:
    def test_a_film_both_users_put_on_the_watchlist_is_a_match(
        self, user, another_user, movie
    ):
        session = make_paired_session(user, another_user)
        candidate = add_candidate(session, movie, 1)
        swipe(user, candidate, SwipeAction.WATCHLIST)
        swipe(another_user, candidate, SwipeAction.WATCHLIST)

        matches = list(matched_candidates(session))

        assert [c.pk for c in matches] == [candidate.pk]
        assert matches[0].watchlist_count == 2

    def test_a_film_only_one_user_liked_is_not_a_match(
        self, user, another_user, movie, another_movie
    ):
        session = make_paired_session(user, another_user)
        half_liked = add_candidate(session, movie, 1)
        skipped = add_candidate(session, another_movie, 2)
        swipe(user, half_liked, SwipeAction.WATCHLIST)
        swipe(another_user, half_liked, SwipeAction.SKIP)
        swipe(user, skipped, SwipeAction.SKIP)
        swipe(another_user, skipped, SwipeAction.SKIP)

        assert list(matched_candidates(session)) == []

    def test_candidates_without_swipes_are_not_matches(self, user, another_user, movie):
        session = make_paired_session(user, another_user)
        add_candidate(session, movie, 1)

        assert list(matched_candidates(session)) == []

    def test_the_most_recent_match_comes_first(
        self, user, another_user, movie, another_movie
    ):
        session = make_paired_session(user, another_user)
        older = add_candidate(session, movie, 1)
        newer = add_candidate(session, another_movie, 2)
        now = timezone.now()
        swipe(user, older, SwipeAction.WATCHLIST, when=now - timedelta(hours=3))
        swipe(another_user, older, SwipeAction.WATCHLIST, when=now - timedelta(hours=2))
        swipe(user, newer, SwipeAction.WATCHLIST, when=now - timedelta(hours=1))
        swipe(another_user, newer, SwipeAction.WATCHLIST, when=now)

        matches = list(matched_candidates(session))

        assert [c.pk for c in matches] == [newer.pk, older.pk]
        assert matches[0].matched_at > matches[1].matched_at

    def test_the_match_time_is_that_of_the_latest_watchlist_swipe(
        self, user, another_user, movie
    ):
        session = make_paired_session(user, another_user)
        candidate = add_candidate(session, movie, 1)
        now = timezone.now()
        swipe(user, candidate, SwipeAction.WATCHLIST, when=now - timedelta(days=1))
        swipe(another_user, candidate, SwipeAction.WATCHLIST, when=now)

        assert list(matched_candidates(session))[0].matched_at == now

    def test_matches_of_other_sessions_are_not_included(
        self, user, another_user, movie
    ):
        mine = make_paired_session(user, another_user)
        other = make_paired_session(user, another_user)
        other_candidate = add_candidate(other, movie, 1)
        swipe(user, other_candidate, SwipeAction.WATCHLIST)
        swipe(another_user, other_candidate, SwipeAction.WATCHLIST)

        assert list(matched_candidates(mine)) == []

    def test_movies_are_loaded_with_the_matches(
        self, user, another_user, movie, django_assert_num_queries
    ):
        session = make_paired_session(user, another_user)
        candidate = add_candidate(session, movie, 1)
        swipe(user, candidate, SwipeAction.WATCHLIST)
        swipe(another_user, candidate, SwipeAction.WATCHLIST)

        with django_assert_num_queries(1):
            titles = [c.movie.title for c in matched_candidates(session)]

        assert titles == [movie.title]


@pytest.mark.django_db
class TestBuildPairedState:
    def test_adds_paired_details_to_the_participant_state(self, user, another_user):
        session = make_paired_session(user, another_user)

        with patch(
            f"{MODULE}.build_participant_state", return_value={"participants": 2}
        ) as base:
            state = build_paired_state(session, user)

        base.assert_called_once_with(session, user)
        assert state == {
            "participants": 2,
            "type": SwipeSessionType.PAIRED,
            "current_user_id": str(user.pk),
            "matches_count": 0,
        }

    def test_counts_the_matches_of_the_session(
        self, user, another_user, movie, another_movie
    ):
        session = make_paired_session(user, another_user)
        for position, film in enumerate([movie, another_movie], start=1):
            candidate = add_candidate(session, film, position)
            swipe(user, candidate, SwipeAction.WATCHLIST)
            swipe(another_user, candidate, SwipeAction.WATCHLIST)

        with patch(f"{MODULE}.build_participant_state", return_value={}):
            state = build_paired_state(session, another_user)

        assert state["matches_count"] == 2
        assert state["current_user_id"] == str(another_user.pk)
