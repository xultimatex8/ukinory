from __future__ import annotations

from unittest.mock import call, patch

import pytest

from apps.common.enums import SwipeAction
from apps.library.models import WatchlistEntry, WatchlistSource
from apps.swipe_sessions.exceptions import CandidateNotFoundError
from apps.swipe_sessions.services.paired import match_payload
from apps.swipe_sessions.services.swipe import (
    _detect_match,
    get_session_candidate,
    record_swipe,
)
from apps.common.enums import SessionStatus, SessionType, SwipeSessionType
from apps.swipe_sessions.models import Swipe, SwipeSession, SwipeSessionCandidate
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

@pytest.fixture
def another_swipe_session(db):
    return SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )

@pytest.fixture
def candidate(swipe_session, movie):
    return SwipeSessionCandidate.objects.create(
        session=swipe_session, movie=movie, score=0.9, position=1
    )



class TestGetSessionCandidate:
    @pytest.mark.django_db
    def test_returns_candidate_from_session(
        self,
        swipe_session,
        candidate,
    ):
        candidate.session = swipe_session
        candidate.save(update_fields=["session"])

        result = get_session_candidate(
            candidate_id=candidate.pk,
            session=swipe_session,
        )

        assert result == candidate

    @pytest.mark.django_db
    def test_raises_when_candidate_does_not_exist(
        self,
        swipe_session,
    ):
        with pytest.raises(CandidateNotFoundError):
            get_session_candidate(
                candidate_id=999999,
                session=swipe_session,
            )

    @pytest.mark.django_db
    def test_raises_when_candidate_belongs_to_another_session(
        self,
        swipe_session,
        another_swipe_session,
        candidate,
    ):
        candidate.session = another_swipe_session
        candidate.save(update_fields=["session"])

        with pytest.raises(CandidateNotFoundError):
            get_session_candidate(
                candidate_id=candidate.pk,
                session=swipe_session,
            )


class TestRecordSwipe:
    @pytest.mark.django_db
    def test_creates_swipe(
        self,
        user,
        candidate,
    ):
        result = record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.SKIP,
        )

        assert result.swipe.user == user
        assert result.swipe.candidate == candidate
        assert result.swipe.action == SwipeAction.SKIP
        assert result.created is True
        assert result.match is None

    @pytest.mark.django_db
    def test_does_not_create_watchlist_entry_for_non_watchlist_action(
        self,
        user,
        candidate,
    ):
        record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.SKIP,
        )

        assert not WatchlistEntry.objects.filter(
            user=user,
            title=candidate.movie.title,
            release_year=candidate.movie.release_year,
        ).exists()

    @pytest.mark.django_db
    def test_watchlist_action_creates_watchlist_entry(
        self,
        user,
        candidate,
    ):
        result = record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.WATCHLIST,
        )

        assert result.swipe.user == user
        assert result.created is True

        entry = WatchlistEntry.objects.get(
            user=user,
            title=candidate.movie.title,
            release_year=candidate.movie.release_year,
        )

        assert entry.movie == candidate.movie
        assert entry.source == WatchlistSource.SWIPE_ADDED
        assert entry.added_date is not None

    @pytest.mark.django_db
    def test_watchlist_action_updates_existing_watchlist_entry(
        self,
        user,
        candidate,
    ):
        old_movie = candidate.movie

        entry = WatchlistEntry.objects.create(
            user=user,
            title=old_movie.title,
            release_year=old_movie.release_year,
            movie=old_movie,
            source=WatchlistSource.SWIPE_ADDED,
        )

        result = record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.WATCHLIST,
        )

        assert result.created is True

        entries = WatchlistEntry.objects.filter(
            user=user,
            title=candidate.movie.title,
            release_year=candidate.movie.release_year,
        )

        assert entries.count() == 1

        entry.refresh_from_db()

        assert entry.movie == candidate.movie
        assert entry.source == WatchlistSource.SWIPE_ADDED


def make_paired_session(*users, status=SessionStatus.ACTIVE):
    session = SwipeSession.objects.create(
        type=SwipeSessionType.PAIRED,
        session_type=SessionType.SWIPE_SESSION,
        status=status,
    )
    session.users.add(*users)
    return session


def add_candidate(session, movie, position=1, score=0.5):
    return SwipeSessionCandidate.objects.create(
        session=session, movie=movie, score=score, position=position
    )


MODULE = "apps.swipe_sessions.services.swipe"


@pytest.fixture
def notify():
    with patch(f"{MODULE}.notify_session") as patched:
        yield patched


def swipe_event(user, candidate, action):
    return {
        "event": "swipe.recorded",
        "user_id": str(user.pk),
        "candidate_id": str(candidate.pk),
        "action": action,
        "title": candidate.movie.title,
        "release_year": candidate.movie.release_year,
    }


@pytest.mark.django_db
class TestRecordSwipeIdempotency:
    def test_repeating_a_swipe_keeps_the_first_decision(self, user, candidate):
        first = record_swipe(user, candidate, SwipeAction.SKIP)
        second = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert second.created is False
        assert second.swipe == first.swipe
        assert second.swipe.action == SwipeAction.SKIP
        assert Swipe.objects.count() == 1
        assert not WatchlistEntry.objects.filter(user=user).exists()

    def test_the_session_is_touched_only_by_the_first_swipe(self, user, candidate):
        with patch(f"{MODULE}.touch_session") as touch:
            record_swipe(user, candidate, SwipeAction.SKIP)
            record_swipe(user, candidate, SwipeAction.SKIP)

        touch.assert_called_once_with(candidate.session_id)

    def test_repeating_a_watchlist_swipe_keeps_a_single_entry(self, user, candidate):
        record_swipe(user, candidate, SwipeAction.WATCHLIST)
        record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert WatchlistEntry.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestRecordSwipeInPairedSessions:
    def paired_candidate(self, user, another_user, movie):
        return add_candidate(make_paired_session(user, another_user), movie)

    def test_no_match_while_the_partner_has_not_swiped(
        self, user, another_user, movie, notify, django_capture_on_commit_callbacks
    ):
        candidate = self.paired_candidate(user, another_user, movie)

        with django_capture_on_commit_callbacks(execute=True):
            outcome = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert outcome.match is None
        assert outcome.created is True
        assert notify.call_args_list == [
            call(candidate.session_id, **swipe_event(user, candidate, SwipeAction.WATCHLIST))
        ]

    def test_a_partner_who_already_wanted_the_film_makes_a_match(
        self, user, another_user, movie, notify, django_capture_on_commit_callbacks
    ):
        candidate = self.paired_candidate(user, another_user, movie)
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.WATCHLIST)

        with django_capture_on_commit_callbacks(execute=True):
            outcome = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        expected = match_payload(candidate)
        assert outcome.match == expected
        assert notify.call_args_list == [
            call(candidate.session_id, **swipe_event(user, candidate, SwipeAction.WATCHLIST)),
            call(candidate.session_id, event="match", **expected),
        ]

    def test_a_match_puts_the_film_on_both_watchlists(
        self, user, another_user, movie
    ):
        candidate = self.paired_candidate(user, another_user, movie)
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.WATCHLIST)

        with patch(f"{MODULE}.notify_session"):
            record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert WatchlistEntry.objects.filter(user=user, movie=movie).exists()
        partner_entry = WatchlistEntry.objects.get(user=another_user, movie=movie)
        assert partner_entry.source == WatchlistSource.SWIPE_MATCH

    def test_a_partner_who_skipped_the_film_does_not_make_a_match(
        self, user, another_user, movie, notify
    ):
        candidate = self.paired_candidate(user, another_user, movie)
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.SKIP)

        outcome = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert outcome.match is None
        assert not WatchlistEntry.objects.filter(user=another_user).exists()

    def test_skipping_after_the_partner_wanted_the_film_is_not_a_match(
        self, user, another_user, movie, notify, django_capture_on_commit_callbacks
    ):
        candidate = self.paired_candidate(user, another_user, movie)
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.WATCHLIST)

        with django_capture_on_commit_callbacks(execute=True):
            outcome = record_swipe(user, candidate, SwipeAction.SKIP)

        assert outcome.match is None
        assert not WatchlistEntry.objects.filter(user=user).exists()
        assert notify.call_args_list == [
            call(candidate.session_id, **swipe_event(user, candidate, SwipeAction.SKIP))
        ]

    def test_the_partners_swipe_on_another_film_does_not_count(
        self, user, another_user, movie, another_movie
    ):
        session = make_paired_session(user, another_user)
        candidate = add_candidate(session, movie, 1)
        other = add_candidate(session, another_movie, 2)
        Swipe.objects.create(user=another_user, candidate=other, action=SwipeAction.WATCHLIST)

        with patch(f"{MODULE}.notify_session"):
            outcome = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert outcome.match is None

    def test_nothing_is_broadcast_before_the_transaction_commits(
        self, user, another_user, movie, notify, django_capture_on_commit_callbacks
    ):
        candidate = self.paired_candidate(user, another_user, movie)

        with django_capture_on_commit_callbacks(execute=False):
            record_swipe(user, candidate, SwipeAction.SKIP)

        notify.assert_not_called()

    def test_the_swipe_is_stored_with_the_chosen_action(
        self, user, another_user, movie, notify
    ):
        candidate = self.paired_candidate(user, another_user, movie)

        outcome = record_swipe(user, candidate, SwipeAction.SKIP)

        assert outcome.swipe.action == SwipeAction.SKIP
        assert outcome.swipe.user == user


@pytest.mark.django_db
class TestSoloSessionsStayQuiet:
    def test_solo_swipes_are_neither_matched_nor_broadcast(
        self, user, another_user, candidate, notify, django_capture_on_commit_callbacks
    ):
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.WATCHLIST)

        with django_capture_on_commit_callbacks(execute=True):
            outcome = record_swipe(user, candidate, SwipeAction.WATCHLIST)

        assert outcome.match is None
        notify.assert_not_called()


@pytest.mark.django_db
class TestDetectMatch:
    def test_actions_other_than_watchlist_never_match_and_cost_no_queries(
        self, user, django_assert_num_queries
    ):
        with django_assert_num_queries(0):
            assert _detect_match(user, None, SwipeAction.SKIP) is None

    def test_without_partner_swipes_there_is_no_match_and_nothing_is_saved(
        self, user, another_user, movie
    ):
        candidate = add_candidate(make_paired_session(user, another_user), movie)

        assert _detect_match(user, candidate, SwipeAction.WATCHLIST) is None
        assert not WatchlistEntry.objects.exists()

    def test_a_partner_watchlist_swipe_gives_the_match_payload(
        self, user, another_user, movie
    ):
        candidate = add_candidate(make_paired_session(user, another_user), movie)
        Swipe.objects.create(user=another_user, candidate=candidate, action=SwipeAction.WATCHLIST)

        assert _detect_match(user, candidate, SwipeAction.WATCHLIST) == match_payload(candidate)

    def test_the_users_own_swipe_is_not_a_partner_swipe(
        self, user, another_user, movie
    ):
        candidate = add_candidate(make_paired_session(user, another_user), movie)
        Swipe.objects.create(user=user, candidate=candidate, action=SwipeAction.WATCHLIST)

        assert _detect_match(user, candidate, SwipeAction.WATCHLIST) is None
