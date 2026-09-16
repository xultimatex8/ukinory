from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.common.enums import SwipeSessionStatus
from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.services.session import (
    create_swipe_session,
    end_swipe_session,
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

        export_watchlist.assert_called_once_with(user=user)

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
