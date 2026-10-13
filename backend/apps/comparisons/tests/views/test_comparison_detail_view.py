import pytest

from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework.test import APIClient

from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
)
from apps.common.exceptions import NotSessionMemberError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestComparisonDetailView:
    @pytest.fixture(autouse=True)
    def setup_url(self):
        self.url = reverse(
            "comparison-detail",
            kwargs={"comparison_id": "comparison-id"},
        )

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.url)

        assert response.status_code == 401

    @patch("apps.comparisons.views.get_comparison_result")
    def test_returns_404_when_comparison_does_not_exist(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = ComparisonNotFoundError

        response = api_client.get(self.url)

        assert response.status_code == 404
        assert response.data == {
            "detail": "Comparison not found.",
        }

        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )

    @patch("apps.comparisons.views.get_comparison_result")
    def test_returns_403_when_user_is_not_a_member(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = NotSessionMemberError

        response = api_client.get(self.url)

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session.",
        }
        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )

    @patch("apps.comparisons.views.get_comparison_result")
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

        response = api_client.get(self.url)

        assert response.status_code == 422
        assert response.data == {
            "detail": "Both participants need imported ratings.",
        }

        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )

    @patch("apps.comparisons.views.attach_participants")
    @patch("apps.comparisons.views.attach_tmdb_metadata")
    @patch("apps.comparisons.views.serialize_result")
    @patch("apps.comparisons.views.get_comparison_result")
    def test_returns_serialized_result(
        self,
        mock_get_result,
        mock_serialize_result,
        mock_attach_tmdb_metadata,
        mock_attach_participants,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        result = MagicMock()
        result.comparison = MagicMock()
        mock_get_result.return_value = result

        serialized = {
            "comparison": "comparison-id",
            "metrics": {"taste_overlap": 0.5},
            "narrative": "You have similar tastes.",
            "recommendations": [],
        }

        with_metadata = {
            **serialized,
            "metadata_attached": True,
        }
        with_participants = {
            **with_metadata,
            "participants_attached": True,
        }

        mock_serialize_result.return_value = serialized
        mock_attach_tmdb_metadata.return_value = with_metadata
        mock_attach_participants.return_value = with_participants

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == with_participants

        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )
        mock_serialize_result.assert_called_once_with(result)
        mock_attach_tmdb_metadata.assert_called_once_with(serialized)
        mock_attach_participants.assert_called_once_with(
            with_metadata,
            result.comparison,
            user,
        )

    @patch("apps.comparisons.views.get_comparison_result")
    def test_returns_default_message_for_empty_insufficient_data_error(
        self,
        mock_get_result,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        mock_get_result.side_effect = InsufficientDataError()

        response = api_client.get(self.url)

        assert response.status_code == 422
        assert response.data == {
            "detail": "Not enough data to compare.",
        }

        mock_get_result.assert_called_once_with(
            user=user,
            comparison_id="comparison-id",
        )
