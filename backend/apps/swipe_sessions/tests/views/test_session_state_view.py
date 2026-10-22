import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient


SESSION_ID = "00000000-0000-0000-0000-000000000001"
SESSION_UUID = uuid.UUID(SESSION_ID)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestPairedSwipeSessionStateView:
    @pytest.fixture(autouse=True)
    def setup_url(self):
        self.url = reverse(
            "paired-swipe-session-state",
            kwargs={"pk": SESSION_ID},
        )

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.url)

        assert response.status_code == 401

    @patch("apps.swipe_sessions.views.build_paired_state")
    @patch("apps.swipe_sessions.views.require_paired")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_returns_paired_state(
        self,
        mock_get_session,
        mock_require_paired,
        mock_build_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        mock_get_session.return_value = session

        expected_state = {
            "id": SESSION_ID,
            "status": "WAITING",
            "partner_joined": False,
        }
        mock_build_state.return_value = expected_state

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == expected_state

        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_require_paired.assert_called_once_with(session)
        mock_build_state.assert_called_once_with(session, user)

    @patch("apps.swipe_sessions.views.build_paired_state")
    @patch("apps.swipe_sessions.views.require_paired")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_does_not_build_state_for_non_paired_session(
        self,
        mock_get_session,
        mock_require_paired,
        mock_build_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        mock_get_session.return_value = session

        error = APIException("Session is not paired.")
        error.status_code = 400
        mock_require_paired.side_effect = error

        response = api_client.get(self.url)

        assert response.status_code == 400
        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_require_paired.assert_called_once_with(session)
        mock_build_state.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(self.url)

        assert response.status_code == 405
