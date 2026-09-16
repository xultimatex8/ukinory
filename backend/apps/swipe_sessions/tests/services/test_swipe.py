from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.common.enums import SwipeAction
from apps.library.models import WatchlistEntry, WatchlistSource
from apps.swipe_sessions.exceptions import CandidateNotFoundError
from apps.swipe_sessions.services.swipe import (
    get_session_candidate,
    record_swipe,
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
        swipe = record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.SKIP,
        )

        assert swipe.user == user
        assert swipe.candidate == candidate
        assert swipe.action == SwipeAction.SKIP

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
        record_swipe(
            user=user,
            candidate=candidate,
            action=SwipeAction.WATCHLIST,
        )

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

        assert result is not None

        entries = WatchlistEntry.objects.filter(
            user=user,
            title=candidate.movie.title,
            release_year=candidate.movie.release_year,
        )

        assert entries.count() == 1

        entry.refresh_from_db()

        assert entry.movie == candidate.movie
        assert entry.source == WatchlistSource.SWIPE_ADDED
