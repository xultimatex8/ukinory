import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_register_view_creates_user(api_client):
    payload = {"email": "ana@example.com", "username": "ana", "password": "Str0ngP4ssw0rd!"}
    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 201
    assert response.data["user"]["email"] == "ana@example.com"
    assert response.data["user"]["is_guest"] is False


@pytest.mark.django_db
def test_register_view_rejects_duplicate_email(api_client, registered_user):
    payload = {"email": registered_user.email, "username": "another", "password": "Str0ngP4ssw0rd!"}
    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400


@pytest.mark.django_db
def test_register_view_rejects_weak_password(api_client):
    payload = {"email": "ana@example.com", "username": "ana", "password": "123456"}
    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400
    assert "password" in response.data
