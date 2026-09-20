from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import pytest

from apps.common.enums import LegalDocumentType
from apps.legal.tests.factories import make_document


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


@pytest.fixture
def current_documents(db):
    terms = make_document(
        LegalDocumentType.TERMS,
        "1",
        days_ago=30,
    )
    privacy = make_document(
        LegalDocumentType.PRIVACY,
        "1",
        days_ago=30,
    )

    return [terms, privacy]
