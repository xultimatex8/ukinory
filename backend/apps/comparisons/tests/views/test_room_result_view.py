import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.common.enums import GenerationStatus
from apps.comparisons.exceptions import InsufficientDataError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRoomResultView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_409_when_room_has_no_comparison(
        self,
        mock_get_user_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        room = MagicMock()
        room.comparison = None
        mock_get_user_room.return_value = room

        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 409
        assert response.data == {
            "detail": "The comparison is not ready yet.",
            "generation_status": None,
        }

    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_409_when_comparison_is_not_ready(
        self,
        mock_get_user_room,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        comparison = MagicMock()
        comparison.generation_status = GenerationStatus.PENDING

        room = MagicMock()
        room.comparison = comparison

        mock_get_user_room.return_value = room

        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 409
        assert response.data == {
            "detail": "The comparison is not ready yet.",
            "generation_status": GenerationStatus.PENDING,
        }

    @patch(
        "apps.comparisons.views.serialize_result"
    )
    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_serialized_result_when_comparison_is_ready(
        self,
        mock_get_user_room,
        mock_get_comparison_result,
        mock_serialize_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        comparison = MagicMock()
        comparison.pk = "comparison-id"
        comparison.generation_status = GenerationStatus.READY

        room = MagicMock()
        room.comparison = comparison

        result = MagicMock()

        mock_get_user_room.return_value = room
        mock_get_comparison_result.return_value = result
        mock_serialize_result.return_value = {
            "comparison": "comparison-id",
            "metrics": {"taste_overlap": 0.5},
            "narrative": "You have similar tastes.",
            "recommendations": [],
        }

        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 200
        assert response.data == {
            "comparison": "comparison-id",
            "metrics": {"taste_overlap": 0.5},
            "narrative": "You have similar tastes.",
            "recommendations": [],
        }

        mock_get_comparison_result.assert_called_once_with(
            user=user,
            comparison_id=comparison.pk,
        )
        mock_serialize_result.assert_called_once_with(result)

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_422_when_there_is_insufficient_data(
        self,
        mock_get_user_room,
        mock_get_comparison_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        comparison = MagicMock()
        comparison.pk = "comparison-id"
        comparison.generation_status = GenerationStatus.READY

        room = MagicMock()
        room.comparison = comparison

        mock_get_user_room.return_value = room
        mock_get_comparison_result.side_effect = InsufficientDataError(
            "Both participants need imported ratings."
        )

        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 422
        assert response.data == {
            "detail": "Both participants need imported ratings.",
        }

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    @patch(
        "apps.comparisons.views.get_user_room"
    )
    def test_returns_default_message_for_empty_insufficient_data_error(
        self,
        mock_get_user_room,
        mock_get_comparison_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        comparison = MagicMock()
        comparison.pk = "comparison-id"
        comparison.generation_status = GenerationStatus.READY

        room = MagicMock()
        room.comparison = comparison

        mock_get_user_room.return_value = room
        mock_get_comparison_result.side_effect = InsufficientDataError()

        response = api_client.get(
            reverse(
                "room-result",
                kwargs={
                    "room_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        )

        assert response.status_code == 422
        assert response.data == {
            "detail": "Not enough data to compare.",
        }
