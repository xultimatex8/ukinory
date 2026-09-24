from unittest.mock import patch

import pytest

from apps.swipe_sessions.views import SwipeSessionRecommendationView


@pytest.mark.django_db
class TestSwipeSessionRecommendationView:
    def test_returns_recommendation(
        self,
        authenticated_get,
        candidate,
        swipe_session,
    ):
        recommendation = candidate

        metadata = {
            "id": 1001,
            "title": "Test Movie",
        }

        with patch(
            "apps.swipe_sessions.views.get_next_recommendation_for_session",
            return_value=(candidate, recommendation),
        ), patch(
            "apps.swipe_sessions.views.fetch_live_display_metadata",
            return_value=metadata,
        ) as mock_metadata:
            request = authenticated_get()

            response = SwipeSessionRecommendationView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 200
        assert response.data == {
            "finished": False,
            "candidate_id": candidate.id,
            "movie": metadata,
        }

        mock_metadata.assert_called_once()

    def test_returns_finished_when_no_recommendation(
        self,
        authenticated_get,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.get_next_recommendation_for_session",
            return_value=None,
        ):
            request = authenticated_get()

            response = SwipeSessionRecommendationView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 200
        assert response.data == {
            "finished": True,
            "candidate_id": None,
            "movie": None,
        }

    def test_returns_404_when_session_not_found(
        self,
        authenticated_get,
        swipe_session,
    ):
        from apps.swipe_sessions.exceptions import SwipeSessionNotFoundError

        with patch(
            "apps.swipe_sessions.views.get_next_recommendation_for_session",
            side_effect=SwipeSessionNotFoundError,
        ):
            request = authenticated_get()

            response = SwipeSessionRecommendationView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 404

    def test_returns_403_when_user_is_not_member(
        self,
        authenticated_get,
        swipe_session,
    ):
        from apps.swipe_sessions.exceptions import NotSessionMemberError

        with patch(
            "apps.swipe_sessions.views.get_next_recommendation_for_session",
            side_effect=NotSessionMemberError,
        ):
            request = authenticated_get()

            response = SwipeSessionRecommendationView.as_view()(
                request,
                pk=swipe_session.id,
            )

        assert response.status_code == 403
