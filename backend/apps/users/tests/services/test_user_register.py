import pytest
from django.contrib.auth import get_user_model

from apps.users.exceptions import UserRegistrationError
from apps.users.services.user_register import register_user


@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

User = get_user_model()


@pytest.mark.django_db
def test_register_user_creates_non_guest():
    user = register_user(email="ana@example.com", username="ana", password="Str0ngP4ssw0rd!")

    assert user.email == "ana@example.com"
    assert user.username == "ana"
    assert user.is_guest is False
    assert user.has_usable_password()


@pytest.mark.django_db
def test_register_user_normalizes_email():
    user = register_user(email="Ana@Example.COM", username="ana", password="Str0ngP4ssw0rd!")

    assert user.email == "Ana@example.com"


@pytest.mark.django_db
def test_register_user_rejects_duplicate_email(user):
    with pytest.raises(UserRegistrationError):
        register_user(email=user.email, username="another", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_guest_cannot_have_email(guest_user):
    from django.db import IntegrityError

    guest_user.email = "ana@example.com"
    with pytest.raises(IntegrityError):
        guest_user.save(update_fields=["email"])


@pytest.mark.django_db
def test_register_user_hashes_the_password():
    user = register_user(email="ana@example.com", username="ana", password="Str0ngP4ssw0rd!")

    assert user.password != "Str0ngP4ssw0rd!"
    assert user.check_password("Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_register_user_persists_exactly_one_user():
    register_user(email="ana@example.com", username="ana", password="Str0ngP4ssw0rd!")

    assert User.objects.filter(email="ana@example.com").count() == 1


@pytest.mark.django_db
def test_register_user_duplicate_message(user):
    with pytest.raises(UserRegistrationError, match="Email already in use"):
        register_user(email=user.email, username="x", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_register_user_duplicate_check_normalizes_the_domain(user):
    local, domain = user.email.split("@")

    with pytest.raises(UserRegistrationError):
        register_user(
            email=f"{local}@{domain.upper()}", username="x", password="Str0ngP4ssw0rd!"
        )


@pytest.mark.django_db
def test_register_user_failed_attempt_creates_nothing(user):
    before = User.objects.count()

    with pytest.raises(UserRegistrationError):
        register_user(email=user.email, username="x", password="Str0ngP4ssw0rd!")

    assert User.objects.count() == before


@pytest.mark.django_db
def test_register_user_without_username():
    user = register_user(email="solo@example.com", password="Str0ngP4ssw0rd!")

    assert user.pk is not None
    assert user.email == "solo@example.com"
    assert user.is_guest is False
