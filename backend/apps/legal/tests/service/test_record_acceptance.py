import pytest
from django.utils import timezone

from apps.legal.exceptions import LegalAcceptanceError
from apps.legal.models import UserLegalAcceptance
from apps.legal.services.record_acceptance import record_acceptance

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
