import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.invites.exceptions import TooManyPendingInvitesError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRoomCreateView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.post(
            reverse("room-create"),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.InviteSerializer"
    )
    @patch(
        "apps.comparisons.views.build_room_state"
    )
    @patch(
        "apps.comparisons.views.create_room"
    )
    def test_creates_room_and_returns_invite(
        self,
        mock_create_room,
        mock_build_room_state,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        room.pk = "room-id"

        invite = MagicMock()
        mock_create_room.return_value = (room, invite)

        mock_build_room_state.return_value = {
            "id": "room-id",
            "status": "WAITING",
            "participants": 1,
            "partner_joined": False,
        }

        mock_serializer.return_value.data = {
            "code": "invite-code",
        }

        response = api_client.post(
            reverse("room-create"),
        )

        assert response.status_code == 201
        assert response.data == {
            "room": {
                "id": "room-id",
                "status": "WAITING",
                "participants": 1,
                "partner_joined": False,
            },
            "invite": {
                "code": "invite-code",
            },
        }

        mock_create_room.assert_called_once_with(user)
        mock_build_room_state.assert_called_once_with(room, user)
        mock_serializer.assert_called_once_with(invite)

    @patch(
        "apps.comparisons.views.create_room"
    )
    def test_returns_429_when_too_many_pending_invites(
        self,
        mock_create_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_create_room.side_effect = TooManyPendingInvitesError

        response = api_client.post(
            reverse("room-create"),
        )

        assert response.status_code == 429
        assert response.data == {
            "detail": "You have too many pending invites.",
        }

    @patch("apps.comparisons.views.InviteSerializer")
    @patch("apps.comparisons.views.build_room_state")
    @patch("apps.comparisons.views.create_room")
    def test_does_not_build_state_when_creation_fails(
        self,
        mock_create_room,
        mock_build_room_state,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_create_room.side_effect = TooManyPendingInvitesError

        response = api_client.post(reverse("room-create"))

        assert response.status_code == 429
        mock_build_room_state.assert_not_called()
        mock_serializer.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("room-create"))

        assert response.status_code == 405
