from uuid import UUID

import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.comparisons.exceptions import (
    RecommendationNotFoundError,
    RoomNotReadyError,
)

ROOM_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api_client():
    return APIClient()


def _url():
    return reverse(
        "room-watchlist-item",
        kwargs={"room_id": ROOM_ID, "movie_id": "42"},
    )


@pytest.mark.django_db
class TestRoomWatchlistItemViewPost:
    def test_requires_authentication(self, api_client):
        response = api_client.post(_url())

        assert response.status_code == 401

    @patch("apps.comparisons.views.add_recommendation_to_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_adds_recommendation_to_watchlist(
        self,
        mock_get_user_room,
        mock_add,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        room = MagicMock()
        mock_get_user_room.return_value = room

        response = api_client.post(_url())

        assert response.status_code == 201
        assert response.data == {"in_watchlist": True}

        mock_get_user_room.assert_called_once_with(
            room_id=UUID(ROOM_ID),
            user=user,
        )
        mock_add.assert_called_once_with(
            room=room,
            user=user,
            movie_id="42",
        )

    @patch("apps.comparisons.views.add_recommendation_to_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_404_when_movie_is_not_recommended(
        self,
        mock_get_user_room,
        mock_add,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_add.side_effect = RecommendationNotFoundError

        response = api_client.post(_url())

        assert response.status_code == 404
        assert response.data == {"detail": "Recommendation not found."}

    @patch("apps.comparisons.views.add_recommendation_to_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_409_when_comparison_is_not_ready(
        self,
        mock_get_user_room,
        mock_add,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_add.side_effect = RoomNotReadyError

        response = api_client.post(_url())

        assert response.status_code == 409
        assert response.data == {"detail": "The comparison is not ready yet."}

    @patch("apps.comparisons.views.add_recommendation_to_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_does_not_add_when_user_is_not_in_room(
        self,
        mock_get_user_room,
        mock_add,
        api_client,
        user,
    ):
        from apps.comparisons.exceptions import NotRoomMemberError

        api_client.force_authenticate(user=user)
        mock_get_user_room.side_effect = NotRoomMemberError

        response = api_client.post(_url())

        assert response.status_code == 403
        mock_add.assert_not_called()


@pytest.mark.django_db
class TestRoomWatchlistItemViewDelete:
    def test_requires_authentication(self, api_client):
        response = api_client.delete(_url())

        assert response.status_code == 401

    @patch("apps.comparisons.views.remove_recommendation_from_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_removes_recommendation_from_watchlist(
        self,
        mock_get_user_room,
        mock_remove,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        room = MagicMock()
        mock_get_user_room.return_value = room

        response = api_client.delete(_url())

        assert response.status_code == 204

        mock_get_user_room.assert_called_once_with(
            room_id=UUID(ROOM_ID),
            user=user,
        )
        mock_remove.assert_called_once_with(
            room=room,
            user=user,
            movie_id="42",
        )

    @patch("apps.comparisons.views.remove_recommendation_from_watchlist")
    @patch("apps.comparisons.views.get_user_room")
    def test_returns_404_when_movie_is_not_recommended(
        self,
        mock_get_user_room,
        mock_remove,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_user_room.return_value = MagicMock()
        mock_remove.side_effect = RecommendationNotFoundError

        response = api_client.delete(_url())

        assert response.status_code == 404
        assert response.data == {"detail": "Recommendation not found."}
