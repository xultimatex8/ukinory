import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_watchlist_export_view_requires_authentication(api_client):
    response = api_client.get(reverse("watchlist-export"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_watchlist_export_view_authenticated(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("watchlist-export"))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert response["Content-Disposition"] == (
        'attachment; filename="ukinory_full_watchlist.csv"'
    )


@pytest.mark.django_db
def test_watchlist_export_view_returns_csv_content(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("watchlist-export"))

    content = response.content.decode("utf-8")

    assert "Title" in content
    assert "Year" in content


@pytest.mark.django_db
def test_watchlist_export_view_returns_empty_watchlist(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("watchlist-export"))

    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert content == "Title,Year\r\n"
