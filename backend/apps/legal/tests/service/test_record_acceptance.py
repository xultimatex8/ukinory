import pytest
from django.utils import timezone

from apps.legal.exceptions import LegalAcceptanceError
from apps.legal.models import UserLegalAcceptance
from apps.legal.services.record_acceptance import record_acceptance
from django.contrib.auth import get_user_model
from types import SimpleNamespace
from apps.common.enums import LegalDocumentType
from apps.legal.tests.factories import make_document


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
def terms_v1(published_documents):
    return published_documents.terms_v1


@pytest.fixture
def terms_v2(published_documents):
    return published_documents.terms_v2


@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]


pytestmark = pytest.mark.django_db


def test_creates_one_row_per_document(user, current_documents):
    record_acceptance(user, current_documents)

    types = user.legal_acceptances.values_list("document__type", flat=True)
    assert sorted(types) == ["PRIVACY", "TERMS"]


def test_returns_the_rows_with_their_documents(user, terms_v2):
    rows = record_acceptance(user, [terms_v2])

    assert [(row.user, row.document) for row in rows] == [(user, terms_v2)]


def test_stamps_accepted_at_with_the_current_time(user, current_documents):
    before = timezone.now()
    rows = record_acceptance(user, current_documents)
    after = timezone.now()

    assert all(before <= row.accepted_at <= after for row in rows)


def test_is_idempotent_per_user_and_document(user, current_documents):
    record_acceptance(user, current_documents)
    record_acceptance(user, current_documents)

    assert UserLegalAcceptance.objects.filter(user=user).count() == 2


def test_keeps_the_history_of_older_versions(user, terms_v1, terms_v2):
    record_acceptance(user, [terms_v1])
    record_acceptance(user, [terms_v2])

    versions = user.legal_acceptances.values_list("document__version", flat=True)
    assert sorted(versions) == ["1", "2"]


def test_only_touches_the_given_user(user, other_user, current_documents):
    record_acceptance(user, current_documents)

    assert not other_user.legal_acceptances.exists()


def test_guests_are_rejected_and_nothing_is_stored(guest_user, current_documents):
    with pytest.raises(LegalAcceptanceError):
        record_acceptance(guest_user, current_documents)

    assert not UserLegalAcceptance.objects.filter(user=guest_user).exists()


def test_a_claimed_guest_can_accept(guest_user, current_documents):
    guest_user.is_guest = False
    guest_user.email = "claimed@example.com"
    guest_user.save()

    record_acceptance(guest_user, current_documents)

    assert guest_user.legal_acceptances.count() == 2


def test_no_documents_returns_empty_list_and_stores_nothing(user):
    assert record_acceptance(user, []) == []
    assert not UserLegalAcceptance.objects.exists()


def test_all_rows_of_one_call_share_the_same_timestamp(user, current_documents):
    rows = record_acceptance(user, current_documents)

    assert len({row.accepted_at for row in rows}) == 1


def test_repeating_keeps_the_original_timestamp(user, current_documents):
    first = {r.document_id: r.accepted_at for r in record_acceptance(user, current_documents)}
    second = {r.document_id: r.accepted_at for r in record_acceptance(user, current_documents)}

    assert second == first


def test_returns_rows_for_documents_that_were_already_accepted(user, current_documents):
    record_acceptance(user, current_documents)

    rows = record_acceptance(user, current_documents)

    assert len(rows) == 2


def test_returns_only_rows_for_the_given_documents(user, terms_v1, terms_v2):
    record_acceptance(user, [terms_v1])

    rows = record_acceptance(user, [terms_v2])

    assert [row.document for row in rows] == [terms_v2]


def test_guest_rejection_explains_why(guest_user, current_documents):
    with pytest.raises(LegalAcceptanceError, match="Guest sessions do not record legal acceptance"):
        record_acceptance(guest_user, current_documents)


def test_guests_are_rejected_even_without_documents(guest_user):
    with pytest.raises(LegalAcceptanceError):
        record_acceptance(guest_user, [])
