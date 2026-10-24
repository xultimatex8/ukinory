from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.common.exceptions import NotSessionMemberError, PartnerNotJoinedError

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRoomGenerateView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.post(
            reverse(
                "room-generate",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.build_room_state"
    )
    @patch(
        "apps.comparisons.views.request_generation"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_requests_generation_and_returns_updated_room(
        self,
        mock_get_user_room,
        mock_request_generation,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        room.pk = "room-id"

        updated_room = MagicMock()
        updated_room.pk = "room-id"

        mock_get_user_room.side_effect = [
            room,
            updated_room,
        ]

        mock_build_room_state.return_value = {
            "id": "room-id",
            "status": "ACTIVE",
            "participants": 2,
            "generation_status": "RUNNING",
        }

        response = api_client.post(
            reverse(
                "room-generate",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 200
        assert response.data == {
            "id": "room-id",
            "status": "ACTIVE",
            "participants": 2,
            "generation_status": "RUNNING",
        }

        assert mock_get_user_room.call_count == 2

        mock_get_user_room.assert_any_call(
            room_id=UUID("00000000-0000-0000-0000-000000000001"),
            user=user,
        )
        mock_request_generation.assert_called_once_with(
            room=room,
        )
        mock_build_room_state.assert_called_once_with(
            updated_room,
            user,
        )

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.request_generation")
    @patch("apps.comparisons.views.get_user_room")
    def test_reloads_room_after_requesting_generation(
        self,
        mock_get_user_room,
        mock_request_generation,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = [MagicMock(), MagicMock()]
        mock_build_room_state.return_value = {}
        loads_before_generation = []
        mock_request_generation.side_effect = (
            lambda **kwargs: loads_before_generation.append(
                mock_get_user_room.call_count
            )
        )

        api_client.post(reverse("room-generate", kwargs={"room_id": ROOM_ID}))

        assert loads_before_generation == [1]
        assert mock_get_user_room.call_count == 2

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.request_generation")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_user_room,
        mock_request_generation,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = NotSessionMemberError

        response = api_client.post(
            reverse("room-generate", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 403
        mock_request_generation.assert_not_called()
        mock_build_room_state.assert_not_called()

    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.request_generation")
    @patch("apps.comparisons.views.get_user_room")
    def test_does_not_return_state_when_generation_request_is_rejected(
        self,
        mock_get_user_room,
        mock_request_generation,
        mock_build_room_state,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_request_generation.side_effect = PartnerNotJoinedError

        response = api_client.post(
            reverse("room-generate", kwargs={"room_id": ROOM_ID}),
        )

        assert 400 <= response.status_code < 500
        mock_build_room_state.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(
            reverse("room-generate", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 405
