import json

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_export_user_data_view_requires_authentication(api_client):
    response = api_client.get(reverse("export-user-data"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_export_user_data_view_authenticated(api_client, registered_user):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("export-user-data"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="account-data-{registered_user.pk}.json"'
    )


@pytest.mark.django_db
def test_export_user_data_view_returns_valid_json(api_client, registered_user):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("export-user-data"))

    data = json.loads(response.content)

    assert "exported_at" in data
    assert "account" in data
    assert "ratings" in data
    assert "watchlist" in data
    assert "swipe_sessions" in data
    assert "swipes" in data
    assert "legal_acceptances" in data


@pytest.mark.django_db
def test_export_user_data_view_returns_authenticated_user_data(
    api_client,
    registered_user,
):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("export-user-data"))

    data = json.loads(response.content)

    assert data["account"]["email"] == registered_user.email
    assert data["account"]["username"] == registered_user.username
    assert data["account"]["is_guest"] == registered_user.is_guest
