from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication


class TrackingJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            now = timezone.now()
            if not user.last_active_at or (now - user.last_active_at).total_seconds() > 60:
                user.last_active_at = now
                user.save(update_fields=["last_active_at"])
        return result
