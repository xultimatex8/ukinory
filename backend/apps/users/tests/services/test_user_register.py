import pytest
from django.contrib.auth import get_user_model

from apps.users.exceptions import UserRegistrationError
from apps.users.services.user_register import register_user

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
def test_register_user_rejects_duplicate_email(registered_user):
    with pytest.raises(UserRegistrationError):
        register_user(email="ana@example.com", username="another", password="Str0ngP4ssw0rd!")


@pytest.mark.django_db
def test_guest_cannot_have_email(guest_user):
    from django.db import IntegrityError

    guest_user.email = "ana@example.com"
    with pytest.raises(IntegrityError):
        guest_user.save(update_fields=["email"])

