import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_guest_view_creates_user_and_returns_tokens(api_client):
    response = api_client.post(reverse("guest"))

    assert response.status_code == 201
    assert response.data["user"]["is_guest"] is True
    assert "access" in response.data
    assert "refresh" in response.data
    assert User.objects.filter(pk=response.data["user"]["id"]).exists()
