import pytest

from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestComparisonDetailView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 401

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    def test_returns_404_when_comparison_does_not_exist(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = ComparisonNotFoundError

        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Comparison not found.",
        }

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = NotComparisonMemberError

        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not part of this comparison.",
        }

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    def test_returns_422_when_there_is_insufficient_data(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = InsufficientDataError(
            "Both participants need imported ratings."
        )

        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 422
        assert response.data == {
            "detail": "Both participants need imported ratings.",
        }

    @patch(
        "apps.comparisons.views.serialize_result"
    )
    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    def test_returns_serialized_result(
        self,
        mock_get_result,
        mock_serialize_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        result = MagicMock()
        mock_get_result.return_value = result
        mock_serialize_result.return_value = {
            "comparison": "comparison-id",
            "metrics": {"taste_overlap": 0.5},
            "narrative": "You have similar tastes.",
            "recommendations": [],
        }

        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 200
        assert response.data == {
            "comparison": "comparison-id",
            "metrics": {"taste_overlap": 0.5},
            "narrative": "You have similar tastes.",
            "recommendations": [],
        }

        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )
        mock_serialize_result.assert_called_once_with(result)

    @patch(
        "apps.comparisons.views.get_comparison_result"
    )
    def test_returns_default_message_for_empty_insufficient_data_error(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = InsufficientDataError()

        response = api_client.get(
            reverse(
                "comparison-detail",
                kwargs={"comparison_id": "comparison-id"},
            ),
        )

        assert response.status_code == 422
        assert response.data == {
            "detail": "Not enough data to compare.",
        }
