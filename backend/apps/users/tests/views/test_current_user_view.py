import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_current_user_view_returns_user(api_client, registered_user):
    api_client.force_authenticate(user=registered_user)

    response = api_client.get(reverse("current-user"))

    assert response.status_code == 200
    assert response.data["email"] == registered_user.email
    assert response.data["username"] == registered_user.username
    assert response.data["is_guest"] is False


@pytest.mark.django_db
def test_current_user_view_requires_authentication(api_client):
    response = api_client.get(reverse("current-user"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_current_user_view_updates_user(api_client, registered_user):
    api_client.force_authenticate(user=registered_user)

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
def test_current_user_view_rejects_duplicate_email(api_client, registered_user):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    another_user = User.objects.create_user(
        email="another@example.com",
        username="another",
        password="Str0ngP4ssw0rd!",
    )

    api_client.force_authenticate(user=registered_user)

    payload = {
        "email": another_user.email,
        "username": registered_user.username,
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
