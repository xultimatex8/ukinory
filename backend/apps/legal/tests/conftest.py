from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.common.enums import LegalDocumentType

from .factories import make_document

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def guest_user(db):
    return User.objects.create_user(is_guest=True)


@pytest.fixture
def terms_v1(db):
    return make_document(LegalDocumentType.TERMS, "1", days_ago=30)


@pytest.fixture
def terms_v2(db):
    return make_document(LegalDocumentType.TERMS, "2", days_ago=5)


@pytest.fixture
def privacy_v1(db):
    return make_document(LegalDocumentType.PRIVACY, "1", days_ago=30)


@pytest.fixture
def published_documents(terms_v1, terms_v2, privacy_v1):
    return SimpleNamespace(terms_v1=terms_v1, terms_v2=terms_v2, privacy_v1=privacy_v1)


@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]
