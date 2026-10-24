from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.common.exceptions import (
    NotSessionMemberError,
    SessionClosedError,
    SessionNotFoundError,
)

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRoomDetailView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.get(
            reverse(
                "room-detail",
                kwargs={"room_id": "00000000-0000-0000-0000-000000000001"},
            ),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.build_room_state"
    )
    @patch(
        "apps.comparisons.views.heartbeat_room"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_room_state_and_sends_heartbeat(
        self,
        mock_get_user_room,
        mock_heartbeat_room,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        room.pk = "room-id"

        mock_get_user_room.return_value = room
        mock_build_room_state.return_value = {
            "id": "room-id",
            "status": "WAITING",
            "participants": 1,
            "partner_joined": False,
        }

        response = api_client.get(
            reverse(
                "room-detail",
                kwargs={"room_id": "00000000-0000-0000-0000-000000000001"},
            ),
        )

        assert response.status_code == 200
        assert response.data == {
            "id": "room-id",
            "status": "WAITING",
            "participants": 1,
            "partner_joined": False,
        }

        mock_get_user_room.assert_called_once_with(
            room_id=UUID("00000000-0000-0000-0000-000000000001"),
            user=user,
        )
        mock_heartbeat_room.assert_called_once_with(room)
        mock_build_room_state.assert_called_once_with(room, user)

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.heartbeat_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_user_room,
        mock_heartbeat_room,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = NotSessionMemberError

        response = api_client.get(
            reverse("room-detail", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session.",
        }
        mock_heartbeat_room.assert_not_called()
        mock_build_room_state.assert_not_called()

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.heartbeat_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_404_when_room_does_not_exist(
        self,
        mock_get_user_room,
        mock_heartbeat_room,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = SessionNotFoundError

        response = api_client.get(
            reverse("room-detail", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 404
        mock_heartbeat_room.assert_not_called()
        mock_build_room_state.assert_not_called()

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.heartbeat_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_does_not_return_state_when_room_was_closed_by_heartbeat(
        self,
        mock_get_user_room,
        mock_heartbeat_room,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_heartbeat_room.side_effect = SessionClosedError

        response = api_client.get(
            reverse("room-detail", kwargs={"room_id": ROOM_ID}),
        )

        assert 400 <= response.status_code < 500
        mock_build_room_state.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            reverse("room-detail", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 405
