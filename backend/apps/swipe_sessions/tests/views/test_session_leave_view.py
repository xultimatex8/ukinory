from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.common.exceptions import NotSessionMemberError, SessionNotFoundError
from apps.common.services.sessions import LeaveOutcome
from apps.swipe_sessions.views import SwipeSessionLeaveView


@pytest.fixture
def authenticated_delete(user):
    def _make_request(path="/"):
        request = APIRequestFactory().delete(path)
        force_authenticate(request, user=user)
        return request

    return _make_request


@pytest.mark.django_db
class TestSwipeSessionLeaveView:
    def test_leaves_session_and_returns_204(
        self,
        authenticated_delete,
        user,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ) as mock_get, patch(
            "apps.swipe_sessions.views.leave_swipe_session",
            return_value=LeaveOutcome.LEFT,
        ) as mock_leave:
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 204
        assert response.data is None

        mock_get.assert_called_once_with(
            session_id=swipe_session.id,
            user=user,
        )
        mock_leave.assert_called_once_with(
            user=user,
            session=swipe_session,
        )

    @pytest.mark.parametrize("outcome", list(LeaveOutcome))
    def test_returns_204_for_every_leave_outcome(
        self,
        authenticated_delete,
        swipe_session,
        outcome,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.leave_swipe_session",
            return_value=outcome,
        ):
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 204

    def test_returns_404_when_session_not_found(
        self,
        authenticated_delete,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=SessionNotFoundError,
        ), patch(
            "apps.swipe_sessions.views.leave_swipe_session",
        ) as mock_leave:
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Session not found."
        }
        mock_leave.assert_not_called()

    def test_returns_403_when_user_is_not_member(
        self,
        authenticated_delete,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=NotSessionMemberError,
        ), patch(
            "apps.swipe_sessions.views.leave_swipe_session",
        ) as mock_leave:
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session."
        }
        mock_leave.assert_not_called()

    def test_returns_404_when_session_disappears_while_leaving(
        self,
        authenticated_delete,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.leave_swipe_session",
            side_effect=SessionNotFoundError,
        ):
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Session not found."
        }

    def test_returns_403_when_membership_is_lost_while_leaving(
        self,
        authenticated_delete,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.leave_swipe_session",
            side_effect=NotSessionMemberError,
        ):
            request = authenticated_delete()

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session."
        }

    def test_requires_authentication(
        self,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
        ) as mock_get, patch(
            "apps.swipe_sessions.views.leave_swipe_session",
        ) as mock_leave:
            request = APIRequestFactory().delete("/")

            response = SwipeSessionLeaveView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code in (401, 403)
        mock_get.assert_not_called()
        mock_leave.assert_not_called()

    def test_only_allows_delete(
        self,
        user,
        swipe_session,
    ):
        request = APIRequestFactory().post("/")
        force_authenticate(request, user=user)

        response = SwipeSessionLeaveView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 405
