import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


@pytest.mark.django_db
def test_delete_account_view_requires_authentication(api_client):
    response = api_client.delete(reverse("delete-account"))

    assert response.status_code == 401


@pytest.mark.django_db
def test_delete_account_view_guest_no_password(api_client, guest_user):
    access = str(RefreshToken.for_user(guest_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.delete(reverse("delete-account"))

    assert response.status_code == 200
    assert not User.objects.filter(pk=guest_user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_registered_requires_password(api_client, registered_user):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.delete(reverse("delete-account"))

    assert response.status_code == 400
    assert User.objects.filter(pk=registered_user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_registered_correct_password(api_client, registered_user):
    access = str(RefreshToken.for_user(registered_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.delete(reverse("delete-account"), {"password": "Str0ngP4ssw0rd!"})

    assert response.status_code == 200
    assert not User.objects.filter(pk=registered_user.pk).exists()
