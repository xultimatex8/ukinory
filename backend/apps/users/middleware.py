from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

ACTIVITY_UPDATE_INTERVAL = timedelta(minutes=5)


class UpdateLastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            now = timezone.now()
            needs_update = (
                user.last_active_at is None
                or (now - user.last_active_at) >= ACTIVITY_UPDATE_INTERVAL
            )
            if needs_update:
                get_user_model().objects.filter(pk=user.pk).update(last_active_at=now)
                user.last_active_at = now

        return response
