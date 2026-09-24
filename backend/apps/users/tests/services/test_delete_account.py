import pytest
from django.contrib.auth import get_user_model

from apps.users.exceptions import DeleteAccountError
from apps.users.services.delete_account import delete_account

User = get_user_model()


@pytest.mark.django_db
def test_delete_account_guest_no_password_needed(guest_user):
    pk = guest_user.pk
    delete_account(guest_user)

    assert not User.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_account_registered_without_password_raises(registered_user):
    with pytest.raises(DeleteAccountError):
        delete_account(registered_user)


@pytest.mark.django_db
def test_delete_account_registered_wrong_password_raises(registered_user):
    with pytest.raises(DeleteAccountError):
        delete_account(registered_user, password="incorrect_password")


@pytest.mark.django_db
def test_delete_account_registered_correct_password_deletes(registered_user):
    pk = registered_user.pk
    delete_account(registered_user, password="Str0ngP4ssw0rd!")

    assert not User.objects.filter(pk=pk).exists()
