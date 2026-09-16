from unittest.mock import patch

import pytest

from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.views import SwipeSessionStartView


@pytest.mark.django_db
class TestSwipeSessionStartView:
    def test_starts_session(
        self,
        authenticated_post,
        user,
        swipe_session,
    ):
        started_session = swipe_session

        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.start_swipe_session",
            return_value=started_session,
        ) as mock_start:
            request = authenticated_post()

            response = SwipeSessionStartView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 200
        assert response.data["id"] == str(swipe_session.id)

        mock_start.assert_called_once_with(
            user,
            swipe_session,
        )

    def test_returns_404_when_session_not_found(
        self,
        authenticated_post,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=SwipeSessionNotFoundError,
        ):
            request = authenticated_post()

            response = SwipeSessionStartView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Swipe session not found."
        }

    def test_returns_403_when_user_is_not_member(
        self,
        authenticated_post,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=NotSessionMemberError,
        ):
            request = authenticated_post()

            response = SwipeSessionStartView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session."
        }

    def test_returns_400_when_session_cannot_be_started(
        self,
        authenticated_post,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.start_swipe_session",
            side_effect=ValueError("Session cannot be started."),
        ):
            request = authenticated_post()

            response = SwipeSessionStartView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 400
        assert response.data == {
            "detail": "Session cannot be started."
        }

    def test_requires_authentication(
        self,
        api_factory,
        swipe_session,
    ):
        request = api_factory.post("/")

        response = SwipeSessionStartView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 401
