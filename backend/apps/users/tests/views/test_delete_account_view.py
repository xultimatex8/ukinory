import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from apps.library.models import Rating
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

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
def test_delete_account_view_registered_requires_password(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.delete(reverse("delete-account"))

    assert response.status_code == 400
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_registered_correct_password(api_client, user):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.delete(reverse("delete-account"), {"password": "testpass123"})

    assert response.status_code == 200
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_confirms_the_deletion(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    response = api_client.delete(reverse("delete-account"))

    assert response.data == {"detail": "Account successfully deleted!"}


@pytest.mark.django_db
def test_delete_account_view_guest_ignores_a_supplied_password(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    response = api_client.delete(reverse("delete-account"), {"password": "whatever"})

    assert response.status_code == 200
    assert not User.objects.filter(pk=guest_user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_rejects_wrong_password(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse("delete-account"), {"password": "wrong"})

    assert response.status_code == 400
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_rejects_empty_password(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse("delete-account"), {"password": ""})

    assert response.status_code == 400
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_removes_the_users_ratings(api_client, user):
    Rating.objects.create(
        user=user, title="Dune", release_year=2021, rating=4.0, liked=True
    )
    api_client.force_authenticate(user=user)

    api_client.delete(reverse("delete-account"), {"password": "testpass123"})

    assert not Rating.objects.filter(title="Dune").exists()


@pytest.mark.django_db
def test_delete_account_view_does_not_delete_other_users(
    api_client, user, another_user
):
    api_client.force_authenticate(user=user)

    api_client.delete(reverse("delete-account"), {"password": "testpass123"})

    assert User.objects.filter(pk=another_user.pk).exists()


@pytest.mark.django_db
def test_delete_account_view_rejects_unsupported_methods(api_client, user):
    api_client.force_authenticate(user=user)

    assert api_client.post(reverse("delete-account")).status_code == 405
