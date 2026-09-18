import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_change_password_view_updates_password(api_client, registered_user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    registered_user.set_password(old_password)
    registered_user.save(update_fields=["password"])

    api_client.force_authenticate(user=registered_user)

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

    registered_user.refresh_from_db()
    assert registered_user.check_password(new_password)
    assert not registered_user.check_password(old_password)


@pytest.mark.django_db
def test_change_password_view_rejects_incorrect_old_password(
    api_client,
    registered_user,
):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    registered_user.set_password(old_password)
    registered_user.save(update_fields=["password"])

    api_client.force_authenticate(user=registered_user)

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
    registered_user,
):
    old_password = "Str0ngP4ssw0rd!"

    registered_user.set_password(old_password)
    registered_user.save(update_fields=["password"])

    api_client.force_authenticate(user=registered_user)

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
