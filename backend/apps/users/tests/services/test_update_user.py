import pytest
from django.contrib.auth import get_user_model

from apps.users.services.update_user import change_password, update_user

User = get_user_model()


@pytest.mark.django_db
def test_update_user_updates_username_and_email(registered_user):
    user = update_user(
        registered_user,
        username="new_username",
        email="new@example.com",
    )

    assert user.username == "new_username"
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_update_user_persists_changes(registered_user):
    update_user(
        registered_user,
        username="new_username",
        email="new@example.com",
    )

    user = User.objects.get(pk=registered_user.pk)

    assert user.username == "new_username"
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_change_password_updates_password(registered_user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    registered_user.set_password(old_password)
    registered_user.save(update_fields=["password"])

    change_password(
        registered_user,
        old_password=old_password,
        new_password=new_password,
    )

    assert registered_user.check_password(new_password)
    assert not registered_user.check_password(old_password)


@pytest.mark.django_db
def test_change_password_persists_password(registered_user):
    old_password = "Str0ngP4ssw0rd!"
    new_password = "N3wStr0ngP4ssw0rd!"

    registered_user.set_password(old_password)
    registered_user.save(update_fields=["password"])

    change_password(
        registered_user,
        old_password=old_password,
        new_password=new_password,
    )

    user = User.objects.get(pk=registered_user.pk)

    assert user.check_password(new_password)
    assert not user.check_password(old_password)
