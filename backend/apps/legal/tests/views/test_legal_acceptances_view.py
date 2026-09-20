import pytest
from django.urls import reverse

from apps.legal.models import UserLegalAcceptance
from apps.legal.tests.factories import create_current_documents

pytestmark = pytest.mark.django_db


def test_my_legal_acceptances_view_returns_user_acceptances(
    api_client,
    user,
):
    documents = create_current_documents()

    api_client.force_authenticate(user)

    UserLegalAcceptance.objects.create(
        user=user,
        document=documents[0],
    )
    UserLegalAcceptance.objects.create(
        user=user,
        document=documents[1],
    )

    response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 200
    assert len(response.data) == 2


def test_my_legal_acceptances_view_returns_empty_list_without_acceptances(
    api_client,
    user,
):
    api_client.force_authenticate(user)

    response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 200
    assert response.data == []


def test_my_legal_acceptances_view_requires_authentication(api_client):
    response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 401


def test_my_legal_acceptances_view_returns_only_current_user_acceptances(
    api_client,
    user,
    other_user,
):
    documents = create_current_documents()

    UserLegalAcceptance.objects.create(
        user=user,
        document=documents[0],
    )
    UserLegalAcceptance.objects.create(
        user=other_user,
        document=documents[1],
    )

    api_client.force_authenticate(user)

    response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 200
    assert len(response.data) == 1
