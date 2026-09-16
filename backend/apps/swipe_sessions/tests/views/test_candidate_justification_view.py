from unittest.mock import Mock, patch

import pytest

from apps.swipe_sessions.exceptions import (
    CandidateNotFoundError,
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.views import SwipeSessionCandidateJustificationView


@pytest.fixture
def justification():
    return Mock(
        text="This movie matches your taste.",
        language="en",
    )


@pytest.mark.django_db
class TestSwipeSessionCandidateJustificationView:
    def test_returns_justification(
        self,
        authenticated_post,
        candidate,
        swipe_session,
        justification,
    ):
        with patch(
            "apps.swipe_sessions.views.get_candidate_justification",
            return_value=(candidate, justification),
        ):
            request = authenticated_post()

            response = SwipeSessionCandidateJustificationView.as_view()(
                request,
                pk=swipe_session.id,
                candidate_id=candidate.id,
            )

        assert response.status_code == 200
        assert response.data == {
            "candidate_id": candidate.id,
            "justification": "This movie matches your taste.",
            "language": "en",
        }

    @pytest.mark.parametrize(
        ("exception", "expected_status", "expected_detail"),
        [
            (
                SwipeSessionNotFoundError,
                404,
                "Swipe session not found.",
            ),
            (
                NotSessionMemberError,
                403,
                "You are not a member of this session.",
            ),
            (
                CandidateNotFoundError,
                404,
                "Candidate not found.",
            ),
        ],
    )
    def test_handles_service_errors(
        self,
        authenticated_post,
        swipe_session,
        candidate,
        exception,
        expected_status,
        expected_detail,
    ):
        with patch(
            "apps.swipe_sessions.views.get_candidate_justification",
            side_effect=exception,
        ):
            request = authenticated_post()

            response = SwipeSessionCandidateJustificationView.as_view()(
                request,
                pk=swipe_session.id,
                candidate_id=candidate.id,
            )

        assert response.status_code == expected_status
        assert response.data == {
            "detail": expected_detail,
        }
