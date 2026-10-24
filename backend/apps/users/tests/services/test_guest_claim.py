import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.exceptions import GuestClaimError
from apps.users.services.guest_claim import claim_guest
from django.contrib.auth import get_user_model


@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

User = get_user_model()


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
def test_claim_guest_rejects_non_guest(user):
    with pytest.raises(GuestClaimError):
        claim_guest(user, email="another@example.com", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_rejects_duplicate_email(guest_user, user):
    with pytest.raises(GuestClaimError):
        claim_guest(guest_user, email=user.email, password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_blacklists_previous_tokens(guest_user):
    refresh = RefreshToken.for_user(guest_user)
    outstanding = OutstandingToken.objects.get(jti=refresh["jti"])
    assert not BlacklistedToken.objects.filter(token=outstanding).exists()

    claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert BlacklistedToken.objects.filter(token=outstanding).exists()


@pytest.mark.django_db
def test_claim_guest_non_guest_message(user):
    with pytest.raises(GuestClaimError, match="User is not a guest"):
        claim_guest(user, email="x@example.com", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_duplicate_email_message(guest_user, user):
    with pytest.raises(GuestClaimError, match="Email already in use"):
        claim_guest(guest_user, email=user.email, password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_claim_guest_duplicate_check_uses_the_normalized_email(guest_user, user):
    local, domain = user.email.split("@")

    with pytest.raises(GuestClaimError):
        claim_guest(
            guest_user, email=f"{local}@{domain.upper()}", password="Str0ngP4ssw0rd!"
        )


@pytest.mark.django_db
def test_claim_guest_normalizes_the_email_domain(guest_user):
    user = claim_guest(guest_user, email="Ana@EXAMPLE.com", password="Str0ngP4ssw0rd!")

    assert user.email == "Ana@example.com"


@pytest.mark.django_db
def test_claim_guest_ignores_an_empty_username(guest_user):
    original = guest_user.username

    user = claim_guest(
        guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!", username=""
    )

    assert user.username == original


@pytest.mark.django_db
def test_claim_guest_returns_the_same_instance_and_hashes_the_password(guest_user):
    user = claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert user is guest_user
    assert user.password != "Str0ngP4ssw0rd!"
    assert user.check_password("Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_failed_claim_leaves_the_guest_untouched(guest_user, user):
    with pytest.raises(GuestClaimError):
        claim_guest(guest_user, email=user.email, password="Str0ngP4ssw0rd!")

    stored = User.objects.get(pk=guest_user.pk)
    assert stored.is_guest is True
    assert not stored.has_usable_password()


@pytest.mark.django_db
def test_failed_claim_does_not_blacklist_tokens(user):
    refresh = RefreshToken.for_user(user)

    with pytest.raises(GuestClaimError):
        claim_guest(user, email="x@example.com", password="Str0ngP4ssw0rd!")

    assert not BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()


@pytest.mark.django_db
def test_claim_guest_blacklists_every_outstanding_token(guest_user):
    jtis = [RefreshToken.for_user(guest_user)["jti"] for _ in range(3)]

    claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert BlacklistedToken.objects.filter(token__jti__in=jtis).count() == 3


@pytest.mark.django_db
def test_claim_guest_only_blacklists_the_claimants_tokens(guest_user, another_user):
    other = RefreshToken.for_user(another_user)

    claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert not BlacklistedToken.objects.filter(token__jti=other["jti"]).exists()


@pytest.mark.django_db
def test_claim_guest_tolerates_already_blacklisted_tokens(guest_user):
    refresh = RefreshToken.for_user(guest_user)
    refresh.blacklist()

    claim_guest(guest_user, email="ana@example.com", password="Str0ngP4ssw0rd!")

    assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).count() == 1
