from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.enums import LegalDocumentType
from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailableError
from apps.legal.services.acceptance_validation import (
    get_current_documents,
    validate_acceptance,
)

from ..factories import make_document

pytestmark = pytest.mark.django_db


@pytest.mark.usefixtures("published_documents")
def test_get_current_documents_returns_the_newest_effective_version_of_each_type():
    current = {d.type: d.version for d in get_current_documents()}

    assert current == {"TERMS": "2", "PRIVACY": "1"}


@pytest.mark.usefixtures("published_documents")
def test_get_current_documents_ignores_scheduled_versions():
    make_document(LegalDocumentType.TERMS, "3", days_ago=-10)

    current = {d.type: d.version for d in get_current_documents()}

    assert current["TERMS"] == "2"


@pytest.mark.usefixtures("published_documents")
def test_get_current_documents_respects_at():
    at = timezone.now() - timedelta(days=10)

    current = {d.type: d.version for d in get_current_documents(at)}

    assert current["TERMS"] == "1"


@pytest.mark.usefixtures("published_documents")
def test_get_current_documents_puts_terms_before_privacy():
    assert [d.type for d in get_current_documents()] == ["TERMS", "PRIVACY"]


def test_validate_acceptance_accepts_exactly_the_current_documents_and_returns_them(current_documents):
    assert validate_acceptance(current_documents) == current_documents


def test_validate_acceptance_ignores_the_order_of_the_submitted_documents(published_documents):
    validate_acceptance([published_documents.privacy_v1, published_documents.terms_v2])


def test_validate_acceptance_rejects_a_missing_document(published_documents):
    with pytest.raises(LegalAcceptanceError):
        validate_acceptance([published_documents.terms_v2])


@pytest.mark.usefixtures("published_documents")
def test_validate_acceptance_rejects_an_empty_list():
    with pytest.raises(LegalAcceptanceError):
        validate_acceptance([])


def test_validate_acceptance_rejects_a_stale_version(published_documents):
    with pytest.raises(LegalAcceptanceError):
        validate_acceptance([published_documents.terms_v1, published_documents.privacy_v1])


def test_validate_acceptance_rejects_a_scheduled_future_version(published_documents):
    future = make_document(LegalDocumentType.TERMS, "9", days_ago=-3)

    with pytest.raises(LegalAcceptanceError):
        validate_acceptance([future, published_documents.privacy_v1])


def test_validate_acceptance_raises_unavailable_when_a_type_has_no_effective_version(published_documents):
    published_documents.privacy_v1.delete()

    with pytest.raises(LegalDocumentsUnavailableError):
        validate_acceptance([published_documents.terms_v2])
