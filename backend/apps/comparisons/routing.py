from django.urls import re_path

from apps.comparisons.consumers import ComparisonRoomConsumer

websocket_urlpatterns = [
    re_path(r"^ws/comparison-rooms/(?P<room_id>[0-9a-f-]+)/$", ComparisonRoomConsumer.as_asgi()),
]
