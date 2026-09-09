import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_claim_guest_view_requires_authentication(api_client):
    response = api_client.post(reverse("guest-claim"), {"email": "ana@example.com", "password": "Str0ngP4ssw0rd!"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_claim_guest_view_success(api_client, guest_user):
    access = str(RefreshToken.for_user(guest_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    payload = {"email": "ana@example.com", "username": "ana", "password": "Str0ngP4ssw0rd!"}
    response = api_client.post(reverse("guest-claim"), payload)

    assert response.status_code == 200
    assert response.data["user"]["is_guest"] is False
    assert response.data["user"]["email"] == "ana@example.com"


@pytest.mark.django_db
def test_claim_guest_view_rejects_already_registered_user(api_client, registered_user):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    payload = {"email": "another@example.com", "password": "Str0ngP4ssw0rd!"}
    response = api_client.post(reverse("guest-claim"), payload)

    assert response.status_code == 400
