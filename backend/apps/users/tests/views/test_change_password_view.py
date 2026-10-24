import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

@pytest.mark.django_db
def test_change_password_view_updates_password(api_client, user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    user.set_password(old_password)
    user.save(update_fields=["password"])

    api_client.force_authenticate(user=user)

    payload = {
        "old_password": old_password,
        "new_password": new_password,
    }

    response = api_client.post(
        reverse("change-password"),
        payload,
    )

    assert response.status_code == 200
    assert response.data["detail"] == "Password successfully changed."

    user.refresh_from_db()
    assert user.check_password(new_password)
    assert not user.check_password(old_password)


@pytest.mark.django_db
def test_change_password_view_rejects_incorrect_old_password(
    api_client,
    user,
):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    user.set_password(old_password)
    user.save(update_fields=["password"])

    api_client.force_authenticate(user=user)

    payload = {
        "old_password": "WrongPassword123!",
        "new_password": new_password,
    }

    response = api_client.post(
        reverse("change-password"),
        payload,
    )

    assert response.status_code == 400
    assert "old_password" in response.data


@pytest.mark.django_db
def test_change_password_view_rejects_weak_password(
    api_client,
    user,
):
    old_password = "Str0ngP4ssw0rd!"

    user.set_password(old_password)
    user.save(update_fields=["password"])

    api_client.force_authenticate(user=user)

    payload = {
        "old_password": old_password,
        "new_password": "123456",
    }

    response = api_client.post(
        reverse("change-password"),
        payload,
    )

    assert response.status_code == 400
    assert "new_password" in response.data


@pytest.mark.django_db
def test_guest_cannot_change_password(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    payload = {
        "old_password": "Str0ngP4ssw0rd!",
        "new_password": "N3wStr0ngP4ssw0rd!",
    }

    response = api_client.post(
        reverse("change-password"),
        payload,
    )

    assert response.status_code == 400
    assert "Guest accounts cannot change their password" in response.data["detail"]


@pytest.mark.django_db
def test_change_password_view_requires_authentication(api_client):
    payload = {
        "old_password": "Str0ngP4ssw0rd!",
        "new_password": "N3wStr0ngP4ssw0rd!",
    }

    response = api_client.post(
        reverse("change-password"),
        payload,
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_change_password_view_old_password_stops_working(api_client, user):
    api_client.force_authenticate(user=user)

    api_client.post(
        reverse("change-password"),
        {"old_password": "testpass123", "new_password": "N3wStr0ngP4ssw0rd!"},
    )

    user.refresh_from_db()
    assert user.check_password("N3wStr0ngP4ssw0rd!")
    assert not user.check_password("testpass123")


@pytest.mark.django_db
def test_change_password_view_does_not_change_other_users(
    api_client, user, another_user
):
    api_client.force_authenticate(user=user)

    api_client.post(
        reverse("change-password"),
        {"old_password": "testpass123", "new_password": "N3wStr0ngP4ssw0rd!"},
    )

    another_user.refresh_from_db()
    assert another_user.check_password("testpass123")


@pytest.mark.django_db
@pytest.mark.parametrize("missing", ["old_password", "new_password"])
def test_change_password_view_requires_both_passwords(api_client, user, missing):
    payload = {"old_password": "testpass123", "new_password": "N3wStr0ngP4ssw0rd!"}
    del payload[missing]
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("change-password"), payload)

    assert response.status_code == 400
    assert missing in response.data


@pytest.mark.django_db
def test_change_password_view_keeps_the_old_password_when_rejected(
    api_client, user
):
    api_client.force_authenticate(user=user)

    api_client.post(
        reverse("change-password"),
        {"old_password": "testpass123", "new_password": "123456"},
    )

    user.refresh_from_db()
    assert user.check_password("testpass123")


@pytest.mark.django_db
def test_change_password_view_rejects_unsupported_methods(api_client, user):
    api_client.force_authenticate(user=user)

    assert api_client.get(reverse("change-password")).status_code == 405
