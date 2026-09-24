from django.contrib.auth import get_user_model
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.users.exceptions import GuestClaimError


User = get_user_model()


def claim_guest(user, email, password, username=None):
    if not user.is_guest:
        raise GuestClaimError("User is not a guest")

    normalized_email = User.objects.normalize_email(email)
    if User.objects.filter(email=normalized_email).exclude(pk=user.pk).exists():
        raise GuestClaimError("Email already in use")

    user.email = normalized_email
    if username:
        user.username = username
    user.set_password(password)
    user.is_guest = False
    user.save(update_fields=["email", "username", "password", "is_guest"])

    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)

    return user
