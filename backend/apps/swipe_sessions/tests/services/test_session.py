from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.common.enums import SessionStatus
from apps.common.exceptions import (
    InvalidSessionStateError,
    NotSessionMemberError,
    SessionFinishedError,
    SessionNotFoundError,
)
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.session import (
    close_stale_swipe_sessions,
    create_swipe_session,
    end_swipe_session,
    ensure_session_active,
    get_user_swipe_session,
    start_swipe_session,
)


class TestGetUserSwipeSession:
    @pytest.mark.django_db
    def test_returns_session_for_member(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        result = get_user_swipe_session(
            session_id=swipe_session.pk,
            user=user,
        )

        assert result == swipe_session

    @pytest.mark.django_db
    def test_raises_when_session_does_not_exist(self, user):
        with pytest.raises(SessionNotFoundError):
            get_user_swipe_session(
                session_id=999999,
                user=user,
            )

    @pytest.mark.django_db
    def test_raises_when_user_is_not_a_member(
        self,
        user,
        swipe_session,
    ):
        with pytest.raises(NotSessionMemberError):
            get_user_swipe_session(
                session_id=swipe_session.pk,
                user=user,
            )


class TestCreateSwipeSession:
    @pytest.mark.django_db
    def test_creates_session_with_type_and_user(
        self,
        user,
    ):
        session = create_swipe_session(
            user=user,
            session_type="solo",
        )

        assert session.type == "solo"
        assert session.users.filter(pk=user.pk).exists()

    @pytest.mark.django_db
    def test_creates_session_with_default_status(
        self,
        user,
    ):
        session = create_swipe_session(
            user=user,
            session_type="solo",
        )

        assert session.status == SessionStatus.WAITING


class TestStartSwipeSession:
    @pytest.mark.django_db
    def test_starts_waiting_session(
        self,
        user,
        swipe_session,
    ):
        assert swipe_session.status == SessionStatus.WAITING

        with patch(
            "apps.swipe_sessions.services.session.fill_candidate_pool"
        ) as fill_pool:
            result = start_swipe_session(
                user=user,
                session=swipe_session,
            )

        result.refresh_from_db()

        assert result == swipe_session
        assert result.status == SessionStatus.ACTIVE
        assert result.last_seen_at is not None

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SessionStatus.ACTIVE,
            SessionStatus.FINISHED,
        ],
    )
    def test_rejects_session_that_has_already_started_or_finished(
        self,
        user,
        swipe_session,
        status,
    ):
        swipe_session.status = status
        swipe_session.save(update_fields=["status"])

        with pytest.raises(
            InvalidSessionStateError,
            match="Swipe session has already started or finished.",
        ):
            start_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert swipe_session.status == status

    @pytest.mark.django_db
    def test_fills_candidate_pool(
        self,
        user,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.services.session.fill_candidate_pool"
        ) as fill_pool:
            start_swipe_session(
                user=user,
                session=swipe_session,
            )

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )


class TestEndSwipeSession:
    @pytest.mark.django_db
    def test_ends_active_session(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.save(update_fields=["status"])

        summary = MagicMock()

        with patch(
            "apps.swipe_sessions.services.session.export_watchlist_csv",
            return_value=summary,
        ) as export_watchlist:
            result = end_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert result == summary
        assert swipe_session.status == SessionStatus.FINISHED

        export_watchlist.assert_called_once_with(
            user=user,
            session=swipe_session,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SessionStatus.WAITING,
            SessionStatus.FINISHED,
        ],
    )
    def test_rejects_session_that_is_not_active(
        self,
        user,
        swipe_session,
        status,
    ):
        swipe_session.status = status
        swipe_session.save(update_fields=["status"])

        with pytest.raises(
            InvalidSessionStateError,
            match="Swipe session has not started yet.",
        ):
            end_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert swipe_session.status == status


class TestEnsureSessionActive:
    @pytest.mark.django_db
    def test_allows_active_session_with_recent_last_seen(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=1)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.ACTIVE

    @pytest.mark.django_db
    def test_allows_waiting_session_with_recent_created_at(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.WAITING
        swipe_session.last_seen_at = None
        swipe_session.created_at = timezone.now() - timedelta(minutes=1)
        swipe_session.save(
            update_fields=["status", "last_seen_at", "created_at"]
        )

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.WAITING

    @pytest.mark.django_db
    def test_raises_for_finished_session(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.FINISHED
        swipe_session.save(update_fields=["status"])

        with pytest.raises(SessionFinishedError):
            ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.FINISHED

    @pytest.mark.django_db
    def test_finishes_stale_active_session(
        self,
        user,
        swipe_session,
        django_capture_on_commit_callbacks,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        with patch(
            "apps.swipe_sessions.services.session.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                with pytest.raises(SessionFinishedError):
                    ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.FINISHED

        notify.assert_called_once_with(
            swipe_session.pk,
            event="session.updated",
            reason="ended",
        )

    @pytest.mark.django_db
    def test_deletes_stale_waiting_session_using_created_at(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.WAITING
        swipe_session.last_seen_at = None
        swipe_session.created_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(
            update_fields=["status", "last_seen_at", "created_at"]
        )
        session_id = swipe_session.pk

        with pytest.raises(SessionFinishedError):
            ensure_session_active(swipe_session)

        assert not SwipeSession.objects.filter(pk=session_id).exists()


class TestCloseStaleSwipeSessions:
    @pytest.mark.django_db
    def test_deletes_stale_waiting_and_finishes_stale_active(
        self,
        user,
        django_capture_on_commit_callbacks,
    ):
        stale_waiting = create_swipe_session(user, "solo")
        stale_active = create_swipe_session(user, "solo")
        fresh = create_swipe_session(user, "solo")

        old = timezone.now() - timedelta(minutes=3)
        SwipeSession.objects.filter(pk=stale_waiting.pk).update(last_seen_at=old)
        SwipeSession.objects.filter(pk=stale_active.pk).update(
            status=SessionStatus.ACTIVE,
            last_seen_at=old,
        )
        SwipeSession.objects.filter(pk=fresh.pk).update(
            last_seen_at=timezone.now()
        )

        with patch(
            "apps.swipe_sessions.services.session.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                closed = close_stale_swipe_sessions()

        assert closed == 2
        assert not SwipeSession.objects.filter(pk=stale_waiting.pk).exists()

        stale_active.refresh_from_db()
        fresh.refresh_from_db()

        assert stale_active.status == SessionStatus.FINISHED
        assert fresh.status == SessionStatus.WAITING

        notify.assert_called_once_with(
            stale_active.pk,
            event="session.updated",
            reason="ended",
        )
