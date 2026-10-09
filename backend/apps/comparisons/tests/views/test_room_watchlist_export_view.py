from uuid import UUID

import pytest

from django.urls import resolve, reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.comparisons.exceptions import RoomNotReadyError
from apps.comparisons.views import (
    RoomWatchlistExportView,
    RoomWatchlistItemView,
)

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


def _url():
    return reverse("room-watchlist-export", kwargs={"room_id": ROOM_ID})


class TestRoomWatchlistRouting:
    def test_export_path_is_not_captured_by_item_view(self):
        match = resolve(_url())

        assert match.func.view_class is RoomWatchlistExportView

    def test_movie_path_resolves_to_item_view(self):
        match = resolve(
            reverse(
                "room-watchlist-item",
                kwargs={"room_id": ROOM_ID, "movie_id": "42"},
            )
        )

        assert match.func.view_class is RoomWatchlistItemView


@pytest.mark.django_db
class TestRoomWatchlistExportView:
    def test_requires_authentication(self, api_client):
        response = api_client.get(_url())

        assert response.status_code == 401

    @patch("apps.comparisons.views.export_recommendations_csv")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_csv_attachment(
        self,
        mock_get_user_room,
        mock_export,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        room = MagicMock()
        mock_get_user_room.return_value = room
        mock_export.return_value = ("Title,Year\r\nDune,2021\r\n", 1)

        response = api_client.get(_url())

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert response["Content-Disposition"] == (
            'attachment; filename="ukinory_comparison_watchlist.csv"'
        )
        assert response.content.decode() == "Title,Year\r\nDune,2021\r\n"

        mock_get_user_room.assert_called_once_with(
            room_id=UUID(ROOM_ID),
            user=user,
        )
        mock_export.assert_called_once_with(room=room, user=user)

    @patch("apps.comparisons.views.export_recommendations_csv")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_404_when_nothing_to_export(
        self,
        mock_get_user_room,
        mock_export,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_export.return_value = ("Title,Year\r\n", 0)

        response = api_client.get(_url())

        assert response.status_code == 404
        assert response.data == {
            "detail": "No recommended films in your watchlist yet.",
        }

    @patch("apps.comparisons.views.export_recommendations_csv")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_409_when_comparison_is_not_ready(
        self,
        mock_get_user_room,
        mock_export,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_export.side_effect = RoomNotReadyError

        response = api_client.get(_url())

        assert response.status_code == 409
        assert response.data == {"detail": "The comparison is not ready yet."}
