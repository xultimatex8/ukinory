import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.exceptions import GuestClaimError
from apps.users.services.guest_claim import claim_guest


@pytest.mark.django_db
def test_claim_guest_success_updates_fields(guest_user):
    user = claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!", username="ana")

    user.refresh_from_db()
    assert user.email == "ana@example.com"
    assert user.username == "ana"
    assert user.is_guest is False
    assert user.check_password("Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_keeps_pk(guest_user):
    original_pk = guest_user.pk
    user = claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert user.pk == original_pk


@pytest.mark.django_db
def test_claim_guest_keeps_existing_username_if_not_provided(guest_user):
    original_username = guest_user.username
    user = claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert user.username == original_username


@pytest.mark.django_db
def test_claim_guest_rejects_non_guest(registered_user):
    with pytest.raises(GuestClaimError):
        claim_guest(registered_user, email="another@example.com", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_rejects_duplicate_email(guest_user, registered_user):
    with pytest.raises(GuestClaimError):
        claim_guest(guest_user, email=registered_user.email, password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_blacklists_previous_tokens(guest_user):
    refresh = RefreshToken.for_user(guest_user)
    outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
    assert not BlacklistedToken.objects.filter(token=outstanding).exists()

    claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert BlacklistedToken.objects.filter(token=outstanding).exists()
