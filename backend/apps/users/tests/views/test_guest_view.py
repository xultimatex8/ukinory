import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


User = get_user_model()


@pytest.mark.django_db
def test_guest_view_creates_user_and_returns_tokens(api_client):
    response = api_client.post(reverse("guest"))

    assert response.status_code == 201
    assert response.data["user"]["is_guest"] is True
    assert "access" in response.data
    assert "refresh" in response.data
    assert User.objects.filter(is_guest=True).count() == 1


@pytest.mark.django_db
def test_guest_view_access_token_authenticates_the_guest(api_client):
    response = api_client.post(reverse("guest"))
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    me = api_client.get(reverse("current-user"))

    assert me.status_code == 200
    assert me.data["is_guest"] is True


@pytest.mark.django_db
def test_guest_view_creates_a_new_guest_on_every_call(api_client):
    first = api_client.post(reverse("guest"))
    second = api_client.post(reverse("guest"))

    assert User.objects.filter(is_guest=True).count() == 2
    assert first.data["access"] != second.data["access"]


@pytest.mark.django_db
def test_guest_view_does_not_expose_the_password(api_client):
    response = api_client.post(reverse("guest"))

    assert "password" not in response.data["user"]


@pytest.mark.django_db
def test_guest_has_no_email(api_client):
    api_client.post(reverse("guest"))

    assert not User.objects.get(is_guest=True).email


@pytest.mark.django_db
def test_guest_view_rejects_unsupported_methods(api_client):
    assert api_client.get(reverse("guest")).status_code == 405
