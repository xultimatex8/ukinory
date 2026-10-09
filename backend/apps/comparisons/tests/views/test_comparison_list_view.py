import pytest

from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


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
