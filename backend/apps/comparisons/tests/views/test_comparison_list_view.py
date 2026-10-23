import pytest

from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.enums import SessionType
from apps.comparisons.models import Comparison, ComparisonSession


@pytest.fixture
def api_client():
    return APIClient()


def _comparison(*users):
    room = ComparisonSession.objects.create(
        session_type=SessionType.COMPARISON_SESSION,
    )
    room.users.add(*users)
    return Comparison.objects.create(session=room)


@pytest.mark.django_db
class TestComparisonListView:
    def test_requires_authentication(
        self,
        api_client,
    ):
        response = api_client.get(
            reverse("comparison-list"),
        )

        assert response.status_code == 401

    def test_returns_empty_list_when_user_has_no_comparisons(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.get(
            reverse("comparison-list"),
        )

        assert response.status_code == 200
        assert response.data == []

    @patch("apps.comparisons.views.ComparisonSummarySerializer")
    @patch("apps.comparisons.views.list_comparisons")
    def test_returns_serialized_comparisons_of_the_user(
        self,
        mock_list_comparisons,
        mock_serializer,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)
        queryset = MagicMock()
        mock_list_comparisons.return_value = queryset
        mock_serializer.return_value.data = [{"id": "c1"}, {"id": "c2"}]

        response = api_client.get(reverse("comparison-list"))

        assert response.status_code == 200
        assert response.data == [{"id": "c1"}, {"id": "c2"}]
        mock_list_comparisons.assert_called_once_with(user)
        mock_serializer.assert_called_once_with(queryset, many=True)

    def test_only_lists_comparisons_of_sessions_the_user_belongs_to(
        self,
        api_client,
        user,
        another_user,
    ):
        _comparison(user, another_user)
        _comparison(another_user)
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("comparison-list"))

        assert response.status_code == 200
        assert len(response.data) == 1

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(reverse("comparison-list"))

        assert response.status_code == 405
