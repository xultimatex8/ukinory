import pytest

from apps.common.enums import LegalDocumentType
from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailableError
from apps.legal.models import UserLegalAcceptance
from apps.legal.services.accept import accept_current_documents

from ..factories import make_document

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
