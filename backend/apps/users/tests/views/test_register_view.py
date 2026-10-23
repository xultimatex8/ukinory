import pytest
from django.urls import reverse
import uuid
from django.contrib.auth import get_user_model
from apps.common.enums import LegalDocumentType
from apps.legal.models import UserLegalAcceptance
from apps.legal.tests.factories import make_document
from rest_framework.test import APIClient
from types import SimpleNamespace


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

@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]


User = get_user_model()


@pytest.mark.django_db
def test_register_view_creates_user(api_client, current_documents):
    payload = {
        "email": "ana@example.com",
        "username": "ana",
        "password": "Str0ngP4ssw0rd!",
        "accepted_documents": [str(document.pk) for document in current_documents],
    }

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 201
    assert response.data["user"]["email"] == "ana@example.com"
    assert response.data["user"]["is_guest"] is False


@pytest.mark.django_db
def test_register_view_rejects_duplicate_email(
    api_client,
    user,
    current_documents,
):
    payload = {
        "email": user.email,
        "username": "another",
        "password": "Str0ngP4ssw0rd!",
        "accepted_documents": [str(document.pk) for document in current_documents],
    }

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400


@pytest.mark.django_db
def test_register_view_rejects_weak_password(api_client, current_documents):
    payload = {
        "email": "ana@example.com",
        "username": "ana",
        "password": "123456",
        "accepted_documents": [str(document.pk) for document in current_documents],
    }

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400
    assert "password" in response.data


def _payload(documents, **overrides):
    payload = {
        "email": "ana@example.com",
        "username": "ana",
        "password": "Str0ngP4ssw0rd!",
        "accepted_documents": [str(d.pk) for d in documents],
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_register_view_returns_working_tokens(api_client, current_documents):
    response = api_client.post(reverse("register"), _payload(current_documents))

    assert {"access", "refresh"} <= set(response.data)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = api_client.get(reverse("current-user"))
    assert me.status_code == 200
    assert me.data["email"] == "ana@example.com"


@pytest.mark.django_db
def test_register_view_records_the_accepted_documents(api_client, current_documents):
    api_client.post(reverse("register"), _payload(current_documents))

    user = User.objects.get(email="ana@example.com")
    accepted = set(
        UserLegalAcceptance.objects.filter(user=user).values_list("document_id", flat=True)
    )
    assert accepted == {d.pk for d in current_documents}


@pytest.mark.django_db
def test_register_view_does_not_expose_the_password(api_client, current_documents):
    response = api_client.post(reverse("register"), _payload(current_documents))

    assert "password" not in response.data["user"]


@pytest.mark.django_db
def test_register_view_normalizes_the_email_domain(api_client, current_documents):
    response = api_client.post(
        reverse("register"), _payload(current_documents, email="Ana@EXAMPLE.com")
    )

    assert response.status_code == 201
    assert response.data["user"]["email"] == "Ana@example.com"


@pytest.mark.django_db
def test_register_view_requires_accepted_documents(api_client, current_documents):
    payload = _payload(current_documents)
    del payload["accepted_documents"]

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400
    assert "accepted_documents" in response.data
    assert not User.objects.filter(email="ana@example.com").exists()


@pytest.mark.django_db
def test_register_view_rejects_stale_documents_and_creates_no_user(
    api_client, current_documents
):
    stale = make_document(LegalDocumentType.TERMS, "0", days_ago=90)

    response = api_client.post(
        reverse("register"), _payload([stale, current_documents[1]])
    )

    assert response.status_code == 400
    assert "accepted_documents" in response.data
    assert not User.objects.filter(email="ana@example.com").exists()


@pytest.mark.django_db
def test_register_view_rejects_unknown_documents(api_client, current_documents):
    payload = _payload(current_documents)
    payload["accepted_documents"] = [str(uuid.uuid4())]

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400
    assert not User.objects.filter(email="ana@example.com").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["email", "password"])
def test_register_view_requires_email_and_password(api_client, current_documents, field):
    payload = _payload(current_documents)
    del payload[field]

    response = api_client.post(reverse("register"), payload)

    assert response.status_code == 400
    assert field in response.data


@pytest.mark.django_db
def test_register_view_rejects_invalid_email(api_client, current_documents):
    response = api_client.post(
        reverse("register"), _payload(current_documents, email="not-an-email")
    )

    assert response.status_code == 400
    assert "email" in response.data


@pytest.mark.django_db
def test_register_view_rejects_unsupported_methods(api_client):
    assert api_client.get(reverse("register")).status_code == 405
