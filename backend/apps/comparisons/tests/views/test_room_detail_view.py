from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch


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
        "apps.comparisons.views.touch_room"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_room_state_and_touches_room(
        self,
        mock_get_user_room,
        mock_touch_room,
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
        mock_touch_room.assert_called_once_with(room.pk)
        mock_build_room_state.assert_called_once_with(room, user)
