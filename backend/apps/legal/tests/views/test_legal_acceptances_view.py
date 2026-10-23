import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.legal.models import UserLegalAcceptance
from apps.legal.tests.factories import create_current_documents
from rest_framework.test import APIClient
from types import SimpleNamespace
from apps.common.enums import LegalDocumentType
from apps.legal.tests.factories import make_document


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def published_documents(db):
    return SimpleNamespace(
        terms_v1=make_document(LegalDocumentType.TERMS, "1", days_ago=30),
        terms_v2=make_document(LegalDocumentType.TERMS, "2", days_ago=5),
        privacy_v1=make_document(LegalDocumentType.PRIVACY, "1", days_ago=30),
    )


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


def test_my_legal_acceptances_view_returns_every_accepted_version(
    api_client,
    user,
    published_documents,
):
    for document in (published_documents.terms_v1, published_documents.terms_v2):
        UserLegalAcceptance.objects.create(user=user, document=document)
    api_client.force_authenticate(user)

    response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 200
    assert isinstance(response.data, list)
    assert len(response.data) == 2
    dumped = json.dumps(response.data, default=str)
    assert str(published_documents.terms_v1.pk) in dumped
    assert str(published_documents.terms_v2.pk) in dumped


def test_my_legal_acceptances_view_query_count_does_not_grow(
    api_client,
    user,
    published_documents,
):
    api_client.force_authenticate(user)
    UserLegalAcceptance.objects.create(user=user, document=published_documents.terms_v1)
    with CaptureQueriesContext(connection) as single:
        api_client.get(reverse("my-acceptances"))

    UserLegalAcceptance.objects.create(user=user, document=published_documents.terms_v2)
    UserLegalAcceptance.objects.create(user=user, document=published_documents.privacy_v1)
    with CaptureQueriesContext(connection) as several:
        response = api_client.get(reverse("my-acceptances"))

    assert response.status_code == 200
    assert len(several) <= len(single)


def test_my_legal_acceptances_view_rejects_unsupported_methods(api_client, user):
    api_client.force_authenticate(user)

    response = api_client.post(reverse("my-acceptances"))

    assert response.status_code == 405
