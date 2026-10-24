from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.common.exceptions import NotSessionMemberError
from apps.invites.exceptions import TooManyPendingInvitesError

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRoomInviteView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.post(
            reverse(
                "room-invite",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.InviteSerializer"
    )
    @patch(
        "apps.comparisons.views.regenerate_invite"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_regenerates_invite(
        self,
        mock_get_user_room,
        mock_regenerate_invite,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        invite = MagicMock()

        mock_get_user_room.return_value = room
        mock_regenerate_invite.return_value = invite
        mock_serializer.return_value.data = {
            "code": "new-invite-code",
        }

        response = api_client.post(
            reverse(
                "room-invite",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 201
        assert response.data == {
            "code": "new-invite-code",
        }

        mock_get_user_room.assert_called_once_with(
            room_id=UUID("00000000-0000-0000-0000-000000000001"),
            user=user,
        )
        mock_regenerate_invite.assert_called_once_with(
            user=user,
            room=room,
        )
        mock_serializer.assert_called_once_with(invite)

    @patch(
        "apps.comparisons.views.regenerate_invite"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_429_when_too_many_pending_invites(
        self,
        mock_get_user_room,
        mock_regenerate_invite,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        mock_get_user_room.return_value = room
        mock_regenerate_invite.side_effect = TooManyPendingInvitesError

        response = api_client.post(
            reverse(
                "room-invite",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 429
        assert response.data == {
            "detail": "You have too many pending invites.",
        }

    @patch("apps.comparisons.views.InviteSerializer")
    @patch("apps.comparisons.views.regenerate_invite")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_user_room,
        mock_regenerate_invite,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = NotSessionMemberError

        response = api_client.post(
            reverse("room-invite", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session.",
        }
        mock_regenerate_invite.assert_not_called()
        mock_serializer.assert_not_called()

    @patch("apps.comparisons.views.InviteSerializer")
    @patch("apps.comparisons.views.regenerate_invite")
    @patch("apps.comparisons.views.get_user_room")
    def test_does_not_serialize_when_regeneration_fails(
        self,
        mock_get_user_room,
        mock_regenerate_invite,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_regenerate_invite.side_effect = TooManyPendingInvitesError

        response = api_client.post(
            reverse("room-invite", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 429
        mock_serializer.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(
            reverse("room-invite", kwargs={"room_id": ROOM_ID}),
        )

        assert response.status_code == 405
