import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def guest_user(db):
    return User.objects.create_user(is_guest=True)


@pytest.fixture
def registered_user(db):
    return User.objects.create_user(
        email="ana@example.com",
        username="ana",
        password="Str0ngP4ssw0rd!",
        is_guest=False,
    )
