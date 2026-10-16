import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings

from apps.comparisons.routing import websocket_urlpatterns as comparison_ws
from apps.swipe_sessions.routing import websocket_urlpatterns as swipe_sessions_ws
from apps.comparisons.ws_auth import JWTQueryAuthMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JWTQueryAuthMiddleware(URLRouter(comparison_ws + swipe_sessions_ws)),
            settings.CORS_ALLOWED_ORIGINS,
        ),
    }
)
