import json

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from apps.library.models import Rating
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

@pytest.mark.django_db
def test_export_user_data_view_requires_authentication(api_client):
    response = api_client.get(reverse("export-user-data"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_export_user_data_view_authenticated(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("export-user-data"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="account-data-{user.pk}.json"'
    )


@pytest.mark.django_db
def test_export_user_data_view_returns_valid_json(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
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
    user,
):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(reverse("export-user-data"))

    data = json.loads(response.content)

    assert data["account"]["email"] == user.email
    assert data["account"]["username"] == user.username
    assert data["account"]["is_guest"] == user.is_guest


@pytest.mark.django_db
def test_export_user_data_view_includes_the_users_ratings(api_client, user):
    Rating.objects.create(
        user=user, title="Dune", release_year=2021, rating=4.5, liked=True
    )
    api_client.force_authenticate(user=user)

    data = json.loads(api_client.get(reverse("export-user-data")).content)

    assert [r["title"] for r in data["ratings"]] == ["Dune"]


@pytest.mark.django_db
def test_export_user_data_view_excludes_other_users_data(
    api_client, user, another_user
):
    Rating.objects.create(
        user=another_user, title="Dune", release_year=2021, rating=4.5, liked=True
    )
    api_client.force_authenticate(user=user)

    data = json.loads(api_client.get(reverse("export-user-data")).content)

    assert data["ratings"] == []


@pytest.mark.django_db
def test_export_user_data_view_keeps_unicode_readable(api_client, user):
    Rating.objects.create(
        user=user, title="Amélie", release_year=2001, rating=5.0, liked=True
    )
    api_client.force_authenticate(user=user)

    text = api_client.get(reverse("export-user-data")).content.decode("utf-8")

    assert "Amélie" in text
    assert "\\u00e9" not in text


@pytest.mark.django_db
def test_export_user_data_view_works_for_guests(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    response = api_client.get(reverse("export-user-data"))

    assert response.status_code == 200
    assert json.loads(response.content)["account"]["is_guest"] is True
    assert response["Content-Disposition"] == (
        f'attachment; filename="account-data-{guest_user.pk}.json"'
    )


@pytest.mark.django_db
def test_export_user_data_view_rejects_unsupported_methods(api_client, user):
    api_client.force_authenticate(user=user)

    assert api_client.post(reverse("export-user-data")).status_code == 405
