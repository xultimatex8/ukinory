from unittest.mock import MagicMock

import pytest

from apps.common.enums import LegalDocumentType
from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailableError
from apps.legal.models import UserLegalAcceptance
from apps.legal.services.accept import accept_current_documents

from ..factories import make_document
from django.contrib.auth import get_user_model
from types import SimpleNamespace


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
def terms_v2(published_documents):
    return published_documents.terms_v2


@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]


pytestmark = pytest.mark.django_db


def test_records_the_current_versions(user, current_documents):
    accept_current_documents(user, current_documents)

    versions = {
        a.document.type: a.document.version
        for a in user.legal_acceptances.select_related("document")
    }
    assert versions == {"TERMS": "2", "PRIVACY": "1"}


def test_older_acceptances_survive_a_new_version(user, current_documents, terms_v2):
    accept_current_documents(user, current_documents)

    make_document(LegalDocumentType.TERMS, "3", days_ago=0)

    assert user.legal_acceptances.count() == 2
    assert user.legal_acceptances.filter(document=terms_v2).exists()


def test_is_idempotent(user, current_documents):
    accept_current_documents(user, current_documents)
    accept_current_documents(user, current_documents)

    assert UserLegalAcceptance.objects.filter(user=user).count() == 2


def test_stale_documents_are_rejected_and_nothing_is_stored(user, published_documents):
    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(user, [published_documents.terms_v1, published_documents.privacy_v1])

    assert not UserLegalAcceptance.objects.exists()


def test_guests_are_rejected_and_nothing_is_stored(guest_user, current_documents):
    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(guest_user, current_documents)

    assert not UserLegalAcceptance.objects.exists()


def test_raises_unavailable_when_a_document_type_is_not_published(user, published_documents):
    published_documents.privacy_v1.delete()

    with pytest.raises(LegalDocumentsUnavailableError):
        accept_current_documents(user, [published_documents.terms_v2])


def test_is_atomic_when_recording_fails_halfway(user, current_documents, monkeypatch):
    def store_one_then_fail(user, documents):
        UserLegalAcceptance.objects.create(user=user, document=documents[0])
        raise RuntimeError("boom")

    monkeypatch.setattr("apps.legal.services.accept.record_acceptance", store_one_then_fail)

    with pytest.raises(RuntimeError):
        accept_current_documents(user, current_documents)

    assert not UserLegalAcceptance.objects.exists()


def test_returns_the_stored_acceptances(user, current_documents):
    rows = accept_current_documents(user, current_documents)

    assert sorted(row.document.type for row in rows) == ["PRIVACY", "TERMS"]
    assert all(row.user == user for row in rows)


def test_partial_submission_is_rejected_and_nothing_is_stored(user, published_documents):
    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(user, [published_documents.terms_v2])

    assert not UserLegalAcceptance.objects.exists()


def test_empty_submission_is_rejected_and_nothing_is_stored(user, current_documents):
    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(user, [])

    assert not UserLegalAcceptance.objects.exists()


def test_requires_reacceptance_after_a_new_version_is_published(user, current_documents):
    accept_current_documents(user, current_documents)
    make_document(LegalDocumentType.TERMS, "3", days_ago=0)

    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(user, current_documents)

    assert user.legal_acceptances.count() == 2


def test_validation_failure_never_reaches_recording(user, published_documents, monkeypatch):
    record = MagicMock()
    monkeypatch.setattr("apps.legal.services.accept.record_acceptance", record)

    with pytest.raises(LegalAcceptanceError):
        accept_current_documents(user, [published_documents.terms_v1, published_documents.privacy_v1])

    record.assert_not_called()


def test_documents_are_validated_before_the_user_is_checked(guest_user, published_documents):
    published_documents.privacy_v1.delete()

    with pytest.raises(LegalDocumentsUnavailableError):
        accept_current_documents(guest_user, [published_documents.terms_v2])


def test_delegates_to_validation_then_recording(user, current_documents, monkeypatch):
    validate = MagicMock()
    record = MagicMock(return_value=["row"])
    monkeypatch.setattr("apps.legal.services.accept.validate_acceptance", validate)
    monkeypatch.setattr("apps.legal.services.accept.record_acceptance", record)

    result = accept_current_documents(user, current_documents)

    validate.assert_called_once_with(current_documents)
    record.assert_called_once_with(user, current_documents)
    assert result == ["row"]
