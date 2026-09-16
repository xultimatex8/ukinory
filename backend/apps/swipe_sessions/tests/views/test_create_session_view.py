from unittest.mock import patch

import pytest

from apps.common.enums import SwipeSessionType
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.views import SwipeSessionListCreateView


@pytest.mark.django_db
class TestSwipeSessionListCreateView:
    def test_creates_swipe_session(
        self,
        authenticated_post,
        user,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.views.create_swipe_session",
            return_value=swipe_session,
        ) as mock_create:
            request = authenticated_post(
                data={
                    "type": SwipeSessionType.INDIVIDUAL,
                }
            )

            response = SwipeSessionListCreateView.as_view()(request)

        assert response.status_code == 201
        assert response.data["id"] == str(swipe_session.id)

        mock_create.assert_called_once_with(
            user=user,
            session_type=SwipeSessionType.INDIVIDUAL,
        )

    def test_rejects_invalid_session_type(
        self,
        authenticated_post,
    ):
        request = authenticated_post(
            data={
                "type": "INVALID",
            }
        )

        response = SwipeSessionListCreateView.as_view()(request)

        assert response.status_code == 400

    def test_requires_authentication(
        self,
        api_factory,
    ):
        request = api_factory.post(
            "/",
            data={"type": SwipeSessionType.INDIVIDUAL},
            format="json",
        )

        response = SwipeSessionListCreateView.as_view()(request)

        assert response.status_code == 401
