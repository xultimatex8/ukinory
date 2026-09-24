from django.contrib.auth import get_user_model

User = get_user_model()


def update_user(user, *, username, email):
    user.username = username
    user.email = email
    user.save(update_fields=["username", "email"])

    return user


def change_password(user, *, old_password, new_password):
    user.set_password(new_password)
    user.save(update_fields=["password"])
