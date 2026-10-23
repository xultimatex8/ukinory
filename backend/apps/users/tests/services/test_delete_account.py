import pytest
from django.contrib.auth import get_user_model

from apps.users.exceptions import DeleteAccountError
from apps.users.services.delete_account import delete_account
from unittest.mock import MagicMock, patch
from apps.library.models import Rating, WatchlistEntry


@pytest.fixture
def guest_user(db):
    return get_user_model().objects.create_user(is_guest=True)

User = get_user_model()


@pytest.mark.django_db
def test_delete_account_guest_no_password_needed(guest_user):
    pk = guest_user.pk
    delete_account(guest_user)

    assert not User.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_account_registered_without_password_raises(user):
    with pytest.raises(DeleteAccountError):
        delete_account(user)


@pytest.mark.django_db
def test_delete_account_registered_wrong_password_raises(user):
    with pytest.raises(DeleteAccountError):
        delete_account(user, password="incorrect_password")


@pytest.mark.django_db
def test_delete_account_registered_correct_password_deletes(user):
    pk = user.pk
    delete_account(user, password="testpass123")

    assert not User.objects.filter(pk=pk).exists()


CLEANUP = "apps.users.services.delete_account.delete_orphaned_sessions"


def _user_mock(*, is_guest, password_ok=True, session_ids=()):
    user = MagicMock()
    user.is_guest = is_guest
    user.check_password.return_value = password_ok
    user.sessions.values_list.return_value = list(session_ids)
    return user


@pytest.mark.django_db
def test_delete_account_missing_password_explains_why(user):
    with pytest.raises(DeleteAccountError, match="Password is required"):
        delete_account(user)


@pytest.mark.django_db
def test_delete_account_empty_password_counts_as_missing(user):
    with pytest.raises(DeleteAccountError, match="Password is required"):
        delete_account(user, password="")

    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_wrong_password_keeps_the_user(user):
    with pytest.raises(DeleteAccountError, match="Incorrect password"):
        delete_account(user, password="incorrect_password")

    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_delete_account_guest_ignores_a_supplied_password(guest_user):
    pk = guest_user.pk

    delete_account(guest_user, password="whatever")

    assert not User.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_account_removes_the_users_library_data(user):
    Rating.objects.create(
        user=user, title="Dune", release_year=2021, rating=4.0, liked=True
    )
    WatchlistEntry.objects.create(
        user=user, title="Alien", release_year=1979
    )

    delete_account(user, password="testpass123")

    assert not Rating.objects.filter(title="Dune").exists()
    assert not WatchlistEntry.objects.filter(title="Alien").exists()


@pytest.mark.django_db
def test_delete_account_does_not_touch_other_users(user, another_user):
    Rating.objects.create(
        user=another_user, title="Dune", release_year=2021, rating=4.0, liked=True
    )

    delete_account(user, password="testpass123")

    assert User.objects.filter(pk=another_user.pk).exists()
    assert Rating.objects.filter(user=another_user).count() == 1


def test_delete_account_cleans_orphaned_sessions_after_deleting_the_user():
    events = []
    user = _user_mock(is_guest=True, session_ids=[1, 2])
    user.delete.side_effect = lambda: events.append("delete")

    with patch(CLEANUP, side_effect=lambda **kw: events.append(("cleanup", kw))):
        delete_account(user)

    assert events == ["delete", ("cleanup", {"session_ids": [1, 2]})]


def test_delete_account_skips_cleanup_without_sessions():
    user = _user_mock(is_guest=True, session_ids=[])

    with patch(CLEANUP) as cleanup:
        delete_account(user)

    user.delete.assert_called_once_with()
    cleanup.assert_not_called()


def test_delete_account_with_wrong_password_deletes_nothing():
    user = _user_mock(is_guest=False, password_ok=False, session_ids=[1])

    with patch(CLEANUP) as cleanup:
        with pytest.raises(DeleteAccountError):
            delete_account(user, password="nope")

    user.check_password.assert_called_once_with("nope")
    user.delete.assert_not_called()
    cleanup.assert_not_called()
