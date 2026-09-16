from unittest.mock import Mock, patch

import pytest

from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.views import SwipeSessionEndView


@pytest.mark.django_db
class TestSwipeSessionEndView:
    def test_ends_session_and_returns_csv(
        self,
        authenticated_post,
        user,
        swipe_session,
    ):
        summary = Mock(
            csv_content="title,year\nTest Movie,2025\n",
        )

        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.end_swipe_session",
            return_value=summary,
        ) as mock_end:
            request = authenticated_post()

            response = SwipeSessionEndView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 200
        assert response.content.decode() == (
            "title,year\nTest Movie,2025\n"
        )

        assert response["Content-Type"] == "text/csv"
        assert (
            response["Content-Disposition"]
            == 'attachment; filename="ukinory_watchlist.csv"'
        )
        assert response["X-Swipe-Session-Ended"] == "true"

        mock_end.assert_called_once_with(
            user=user,
            session=swipe_session,
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

            response = SwipeSessionEndView.as_view()(
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

            response = SwipeSessionEndView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session."
        }
