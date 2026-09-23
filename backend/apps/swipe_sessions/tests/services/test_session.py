from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.common.enums import SwipeSessionStatus
from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    SwipeSessionFinishedError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.services.session import (
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
        with pytest.raises(SwipeSessionNotFoundError):
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

        assert session.status == SwipeSessionStatus.WAITING


class TestStartSwipeSession:
    @pytest.mark.django_db
    def test_starts_waiting_session(
        self,
        user,
        swipe_session,
    ):
        assert swipe_session.status == SwipeSessionStatus.WAITING

        with patch(
            "apps.swipe_sessions.services.session.fill_candidate_pool"
        ) as fill_pool:
            result = start_swipe_session(
                user=user,
                session=swipe_session,
            )

        result.refresh_from_db()

        assert result == swipe_session
        assert result.status == SwipeSessionStatus.ACTIVE
        assert result.last_seen_at is not None

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SwipeSessionStatus.ACTIVE,
            SwipeSessionStatus.FINISHED,
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
            ValueError,
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

        swipe_session.status = SwipeSessionStatus.ACTIVE
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
        assert swipe_session.status == SwipeSessionStatus.FINISHED

        export_watchlist.assert_called_once_with(
            user=user,
            session=swipe_session,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SwipeSessionStatus.WAITING,
            SwipeSessionStatus.FINISHED,
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
            ValueError,
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
    def test_allows_active_session_that_is_not_stale(
        self,
        swipe_session,
    ):
        swipe_session.status = SwipeSessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=1)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SwipeSessionStatus.ACTIVE

    @pytest.mark.django_db
    def test_raises_for_finished_session(
        self,
        swipe_session,
    ):
        swipe_session.status = SwipeSessionStatus.FINISHED
        swipe_session.save(update_fields=["status"])

        with pytest.raises(SwipeSessionFinishedError):
            ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SwipeSessionStatus.FINISHED

    @pytest.mark.django_db
    def test_finishes_stale_session_and_raises(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)
        swipe_session.status = SwipeSessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        summary = MagicMock()

        with patch(
            "apps.swipe_sessions.services.session.export_watchlist_csv",
            return_value=summary,
        ) as export_watchlist:
            with pytest.raises(SwipeSessionFinishedError):
                ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SwipeSessionStatus.FINISHED

        export_watchlist.assert_called_once_with(
            user=user,
            session=swipe_session,
        )

    @pytest.mark.django_db
    def test_does_not_consider_waiting_session_stale(
        self,
        swipe_session,
    ):
        swipe_session.status = SwipeSessionStatus.WAITING
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SwipeSessionStatus.WAITING

    @pytest.mark.django_db
    def test_does_not_consider_session_without_last_seen_stale(
        self,
        swipe_session,
    ):
        swipe_session.status = SwipeSessionStatus.ACTIVE
        swipe_session.last_seen_at = None
        swipe_session.save(update_fields=["status", "last_seen_at"])

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SwipeSessionStatus.ACTIVE
