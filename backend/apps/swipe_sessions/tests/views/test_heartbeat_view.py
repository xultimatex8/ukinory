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
class TestSwipeSessionHeartbeatView:
    @pytest.fixture(autouse=True)
    def setup_url(self):
        self.url = reverse(
            "swipe-session-heartbeat",
            kwargs={"pk": SESSION_ID},
        )

    def test_requires_authentication(self, api_client):
        response = api_client.post(self.url)

        assert response.status_code == 401

    @patch("apps.swipe_sessions.views.touch_session")
    @patch("apps.swipe_sessions.views.ensure_session_active")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_touches_session_and_returns_no_content(
        self,
        mock_get_session,
        mock_ensure_active,
        mock_touch,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        session.pk = SESSION_UUID
        mock_get_session.return_value = session

        response = api_client.post(self.url)

        assert response.status_code == 204
        assert response.content == b""

        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_ensure_active.assert_called_once_with(session)
        mock_touch.assert_called_once_with(SESSION_UUID)

    @patch("apps.swipe_sessions.views.touch_session")
    @patch("apps.swipe_sessions.views.ensure_session_active")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_does_not_touch_inactive_session(
        self,
        mock_get_session,
        mock_ensure_active,
        mock_touch,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        session.pk = SESSION_UUID
        mock_get_session.return_value = session

        error = APIException("Session is not active.")
        error.status_code = 400
        mock_ensure_active.side_effect = error

        response = api_client.post(self.url)

        assert response.status_code == 400
        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_ensure_active.assert_called_once_with(session)
        mock_touch.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.url)

        assert response.status_code == 405
