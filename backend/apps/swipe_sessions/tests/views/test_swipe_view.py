from unittest.mock import patch

import pytest

from apps.common.enums import SwipeAction
from apps.swipe_sessions.exceptions import (
    CandidateNotFoundError,
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.views import SwipeSessionSwipeView


@pytest.mark.django_db
class TestSwipeSessionSwipeView:
    def test_records_swipe(
        self,
        authenticated_post,
        user,
        candidate,
        swipe_session,
    ):
        swipe = type(
            "SwipeResult",
            (),
            {
                "id": "swipe-id",
                "action": SwipeAction.WATCHLIST,
            },
        )()

        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.get_session_candidate",
            return_value=candidate,
        ), patch(
            "apps.swipe_sessions.views.record_swipe",
            return_value=swipe,
        ) as mock_record:
            request = authenticated_post(
                data={
                    "candidate_id": str(candidate.id),
                    "action": SwipeAction.WATCHLIST,
                }
            )

            response = SwipeSessionSwipeView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 201
        assert response.data == {
            "id": "swipe-id",
            "candidate_id": candidate.id,
            "action": SwipeAction.WATCHLIST,
        }

        mock_record.assert_called_once_with(
            user=user,
            candidate=candidate,
            action=SwipeAction.WATCHLIST,
        )

    def test_returns_404_when_session_not_found(
        self,
        authenticated_post,
        candidate,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=SwipeSessionNotFoundError,
        ):
            request = authenticated_post(
                data={
                    "candidate_id": str(candidate.id),
                    "action": SwipeAction.WATCHLIST,
                }
            )

            response = SwipeSessionSwipeView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404

    def test_returns_403_when_user_is_not_member(
        self,
        authenticated_post,
        candidate,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            side_effect=NotSessionMemberError,
        ):
            request = authenticated_post(
                data={
                    "candidate_id": str(candidate.id),
                    "action": SwipeAction.WATCHLIST,
                }
            )

            response = SwipeSessionSwipeView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403

    def test_returns_404_when_candidate_not_found(
        self,
        authenticated_post,
        candidate,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_user_swipe_session",
            return_value=swipe_session,
        ), patch(
            "apps.swipe_sessions.views.get_session_candidate",
            side_effect=CandidateNotFoundError,
        ):
            request = authenticated_post(
                data={
                    "candidate_id": str(candidate.id),
                    "action": SwipeAction.WATCHLIST,
                }
            )

            response = SwipeSessionSwipeView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404

    def test_rejects_invalid_payload(
        self,
        authenticated_post,
        swipe_session,
    ):
        request = authenticated_post(
            data={
                "candidate_id": "not-a-uuid",
                "action": "INVALID",
            }
        )

        response = SwipeSessionSwipeView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 400
