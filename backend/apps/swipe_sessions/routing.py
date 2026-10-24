from django.urls import re_path

from apps.swipe_sessions.consumers import PairedSwipeConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/swipe-sessions/(?P<session_id>[0-9a-f-]+)/$",
        PairedSwipeConsumer.as_asgi(),
    ),
]
