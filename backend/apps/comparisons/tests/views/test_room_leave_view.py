from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.common.exceptions import NotSessionMemberError, SessionNotFoundError

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


def _url():
    return reverse("room-leave", kwargs={"room_id": ROOM_ID})


@pytest.mark.django_db
class TestRoomLeaveView:
    def test_requires_authentication(self, api_client):
        response = api_client.delete(_url())

        assert response.status_code == 401

    @patch("apps.comparisons.views.leave_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_leaves_room_and_returns_204(
        self,
        mock_get_user_room,
        mock_leave_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        room = MagicMock()
        mock_get_user_room.return_value = room

        response = api_client.delete(_url())

        assert response.status_code == 204
        assert not response.content
        mock_get_user_room.assert_called_once_with(
            room_id=UUID(ROOM_ID),
            user=user,
        )
        mock_leave_room.assert_called_once_with(room=room, user=user)

    @patch("apps.comparisons.views.leave_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_user_room,
        mock_leave_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = NotSessionMemberError

        response = api_client.delete(_url())

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session.",
        }
        mock_leave_room.assert_not_called()

    @patch("apps.comparisons.views.leave_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_403_when_leaving_fails_for_non_member(
        self,
        mock_get_user_room,
        mock_leave_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_leave_room.side_effect = NotSessionMemberError

        response = api_client.delete(_url())

        assert response.status_code == 403

    @patch("apps.comparisons.views.leave_room")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_404_when_room_does_not_exist(
        self,
        mock_get_user_room,
        mock_leave_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = SessionNotFoundError

        response = api_client.delete(_url())

        assert response.status_code == 404
        mock_leave_room.assert_not_called()

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(_url())

        assert response.status_code == 405
