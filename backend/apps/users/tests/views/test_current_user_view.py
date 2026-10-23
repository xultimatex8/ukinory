import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

@pytest.mark.django_db
def test_current_user_view_returns_user(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("current-user"))

    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["username"] == user.username
    assert response.data["is_guest"] is False


@pytest.mark.django_db
def test_current_user_view_requires_authentication(api_client):
    response = api_client.get(reverse("current-user"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_current_user_view_updates_user(api_client, user):
    api_client.force_authenticate(user=user)

    payload = {
        "email": "updated@example.com",
        "username": "updated_username",
    }

    response = api_client.patch(
        reverse("current-user"),
        payload,
    )

    assert response.status_code == 200
    assert response.data["email"] == "updated@example.com"
    assert response.data["username"] == "updated_username"


@pytest.mark.django_db
def test_current_user_view_rejects_duplicate_email(api_client, user, another_user):
    api_client.force_authenticate(user=user)

    payload = {
        "email": another_user.email,
        "username": user.username,
    }

    response = api_client.patch(
        reverse("current-user"),
        payload,
    )

    assert response.status_code == 400
    assert "email" in response.data


@pytest.mark.django_db
def test_guest_cannot_update_profile(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    payload = {
        "email": "guest@example.com",
        "username": "new_username",
    }

    response = api_client.patch(
        reverse("current-user"),
        payload,
    )

    assert response.status_code == 400
    assert "Guest accounts cannot be edited" in response.data["detail"]


@pytest.mark.django_db
def test_current_user_view_does_not_expose_the_password(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("current-user"))

    assert "password" not in response.data


@pytest.mark.django_db
def test_current_user_view_returns_guest_accounts(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    response = api_client.get(reverse("current-user"))

    assert response.status_code == 200
    assert response.data["is_guest"] is True


@pytest.mark.django_db
def test_current_user_view_persists_updates(api_client, user):
    api_client.force_authenticate(user=user)

    api_client.patch(
        reverse("current-user"),
        {"email": "updated@example.com", "username": "updated_username"},
    )

    stored = User.objects.get(pk=user.pk)
    assert stored.email == "updated@example.com"
    assert stored.username == "updated_username"


@pytest.mark.django_db
def test_current_user_view_allows_keeping_the_own_email(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("current-user"),
        {"email": user.email, "username": "renamed"},
    )

    assert response.status_code == 200
    assert response.data["username"] == "renamed"


@pytest.mark.django_db
def test_current_user_view_rejects_invalid_email(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("current-user"),
        {"email": "not-an-email", "username": user.username},
    )

    assert response.status_code == 400
    assert "email" in response.data
    assert User.objects.get(pk=user.pk).email == user.email


@pytest.mark.django_db
def test_current_user_view_does_not_edit_other_users(
    api_client, user, another_user
):
    api_client.force_authenticate(user=user)

    api_client.patch(
        reverse("current-user"),
        {"email": "updated@example.com", "username": "updated_username"},
    )

    another_user.refresh_from_db()
    assert another_user.email == "another@example.com"


@pytest.mark.django_db
def test_current_user_view_rejects_unsupported_methods(api_client, user):
    api_client.force_authenticate(user=user)

    assert api_client.post(reverse("current-user")).status_code == 405
    assert api_client.delete(reverse("current-user")).status_code == 405
