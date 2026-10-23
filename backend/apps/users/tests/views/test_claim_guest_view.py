import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from apps.common.enums import LegalDocumentType
from apps.legal.models import UserLegalAcceptance
from apps.legal.tests.factories import make_document
from rest_framework.test import APIClient
from types import SimpleNamespace


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

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
def test_claim_guest_view_requires_authentication(api_client):
    response = api_client.post(
        reverse("guest-claim"),
        {
            "email": "ana@example.com",
            "password": "Str0ngP4ssw0rd!",
        },
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_claim_guest_view_success(api_client, guest_user, current_documents):
    access = str(RefreshToken.for_user(guest_user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    payload = {
        "email": "ana@example.com",
        "username": "ana",
        "password": "Str0ngP4ssw0rd!",
        "accepted_documents": [str(document.pk) for document in current_documents],
    }

    response = api_client.post(reverse("guest-claim"), payload)

    assert response.status_code == 200
    assert response.data["user"]["is_guest"] is False
    assert response.data["user"]["email"] == "ana@example.com"


@pytest.mark.django_db
def test_claim_guest_view_rejects_already_registered_user(
    api_client,
    user,
    current_documents,
):
    access = str(RefreshToken.for_user(user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    payload = {
        "email": "another@example.com",
        "password": "Str0ngP4ssw0rd!",
        "accepted_documents": [str(document.pk) for document in current_documents],
    }

    response = api_client.post(reverse("guest-claim"), payload)

    assert response.status_code == 400


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
def test_claim_guest_view_returns_working_tokens(api_client, guest_user, current_documents):
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(reverse("guest-claim"), _payload(current_documents))

    assert {"access", "refresh"} <= set(response.data)
    api_client.force_authenticate(user=None)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = api_client.get(reverse("current-user"))
    assert me.data["is_guest"] is False
    assert me.data["email"] == "ana@example.com"


@pytest.mark.django_db
def test_claim_guest_view_blacklists_previous_refresh_tokens(
    api_client, guest_user, current_documents
):
    refresh = RefreshToken.for_user(guest_user)
    outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
    api_client.force_authenticate(user=guest_user)

    api_client.post(reverse("guest-claim"), _payload(current_documents))

    assert BlacklistedToken.objects.filter(token=outstanding).exists()


@pytest.mark.django_db
def test_claim_guest_view_records_the_accepted_documents(
    api_client, guest_user, current_documents
):
    api_client.force_authenticate(user=guest_user)

    api_client.post(reverse("guest-claim"), _payload(current_documents))

    accepted = set(
        UserLegalAcceptance.objects.filter(user=guest_user).values_list(
            "document_id", flat=True
        )
    )
    assert accepted == {d.pk for d in current_documents}


@pytest.mark.django_db
def test_claim_guest_view_rejects_duplicate_email_and_keeps_the_guest(
    api_client, guest_user, user, current_documents
):
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(
        reverse("guest-claim"), _payload(current_documents, email=user.email)
    )

    assert response.status_code == 400
    assert User.objects.get(pk=guest_user.pk).is_guest is True


@pytest.mark.django_db
def test_claim_guest_view_rolls_back_when_documents_are_stale(
    api_client, guest_user, current_documents
):
    refresh = RefreshToken.for_user(guest_user)
    stale = make_document(LegalDocumentType.TERMS, "0", days_ago=90)
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(
        reverse("guest-claim"), _payload([stale, current_documents[1]])
    )

    assert response.status_code == 400
    assert "accepted_documents" in response.data
    assert User.objects.get(pk=guest_user.pk).is_guest is True
    assert not UserLegalAcceptance.objects.filter(user=guest_user).exists()
    assert not BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()


@pytest.mark.django_db
def test_claim_guest_view_requires_accepted_documents(
    api_client, guest_user, current_documents
):
    payload = _payload(current_documents)
    del payload["accepted_documents"]
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(reverse("guest-claim"), payload)

    assert response.status_code == 400
    assert "accepted_documents" in response.data
    assert User.objects.get(pk=guest_user.pk).is_guest is True


@pytest.mark.django_db
def test_claim_guest_view_rejects_weak_password(api_client, guest_user, current_documents):
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(
        reverse("guest-claim"), _payload(current_documents, password="123456")
    )

    assert response.status_code == 400
    assert "password" in response.data


@pytest.mark.django_db
def test_claim_guest_view_rejects_invalid_email(api_client, guest_user, current_documents):
    api_client.force_authenticate(user=guest_user)

    response = api_client.post(
        reverse("guest-claim"), _payload(current_documents, email="not-an-email")
    )

    assert response.status_code == 400
    assert "email" in response.data


@pytest.mark.django_db
def test_claim_guest_view_rejects_unsupported_methods(api_client, guest_user):
    api_client.force_authenticate(user=guest_user)

    assert api_client.get(reverse("guest-claim")).status_code == 405
