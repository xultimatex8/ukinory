import pytest
from django.contrib.auth import get_user_model

from apps.users.services.update_user import change_password, update_user


User = get_user_model()


@pytest.mark.django_db
def test_update_user_updates_username_and_email(user):
    user = update_user(
        user,
        username="new_username",
        email="new@example.com",
    )

    assert user.username == "new_username"
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_update_user_persists_changes(user):
    update_user(
        user,
        username="new_username",
        email="new@example.com",
    )

    user = User.objects.get(pk=user.pk)

    assert user.username == "new_username"
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_change_password_updates_password(user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    user.set_password(old_password)
    user.save(update_fields=["password"])

    change_password(
        user,
        old_password=old_password,
        new_password=new_password,
    )

    assert user.check_password(new_password)
    assert not user.check_password(old_password)


@pytest.mark.django_db
def test_change_password_persists_password(user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    user.set_password(old_password)
    user.save(update_fields=["password"])

    change_password(
        user,
        old_password=old_password,
        new_password=new_password,
    )

    user = User.objects.get(pk=user.pk)

    assert user.check_password(new_password)
    assert not user.check_password(old_password)


@pytest.mark.django_db
def test_update_user_returns_the_same_instance(user):
    assert update_user(user, username="n", email="n@example.com") is user


@pytest.mark.django_db
def test_update_user_keeps_the_password(user):
    update_user(user, username="n", email="n@example.com")

    stored = User.objects.get(pk=user.pk)
    assert stored.check_password("testpass123")


@pytest.mark.django_db
def test_update_user_only_writes_username_and_email(user):
    user.is_guest = True

    update_user(user, username="n", email="n@example.com")

    assert User.objects.get(pk=user.pk).is_guest is False


@pytest.mark.django_db
def test_change_password_hashes_the_new_password(user):
    change_password(
        user, old_password="testpass123", new_password="N3wStr0ngP4ssw0rd!"
    )

    assert user.password != "N3wStr0ngP4ssw0rd!"


@pytest.mark.django_db
def test_change_password_only_writes_the_password(user):
    original_username = user.username
    user.username = "changed-in-memory"

    change_password(
        user, old_password="testpass123", new_password="N3wStr0ngP4ssw0rd!"
    )

    assert User.objects.get(pk=user.pk).username == original_username


@pytest.mark.django_db
def test_change_password_does_not_affect_other_users(user, another_user):
    change_password(
        user, old_password="testpass123", new_password="N3wStr0ngP4ssw0rd!"
    )

    another_user.refresh_from_db()
    assert another_user.check_password("testpass123")
