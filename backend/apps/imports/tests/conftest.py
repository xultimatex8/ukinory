import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


User = get_user_model()


@pytest.fixture
def registered_user(db):
    return User.objects.create_user(
        email="importer@example.com",
        username="importer",
        password="Str0ngP4ssw0rd!",
        is_guest=False,
    )


@pytest.fixture
def api_client(registered_user):
    client = APIClient()
    client.force_authenticate(user=registered_user)
    return client
