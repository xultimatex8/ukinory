from django.contrib.auth import get_user_model

from apps.users.exceptions import UserRegistrationError


User = get_user_model()


def register_user(email, password, username=None):
    normalized_email = User.objects.normalize_email(email)

    if User.objects.filter(email=normalized_email, is_guest=False).exists():
        raise UserRegistrationError("Email already in use")

    return User.objects.create_user(
        email=normalized_email,
        username=username,
        password=password,
        is_guest=False,
    )
