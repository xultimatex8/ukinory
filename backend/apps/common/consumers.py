from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError

from apps.common.models import Session
from apps.common.realtime import group_name

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


class BaseSessionConsumer(AsyncJsonWebsocketConsumer):
    model = Session
    extra_filters: dict = {}
    connected_event = "session.updated"

    async def connect(self):
        user = self.scope.get("user")
        session_id = self.scope["url_route"]["kwargs"]["session_id"]

        if user is None or not user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        if not await self._is_member(user, session_id):
            await self.close(code=CLOSE_FORBIDDEN)
            return

        self.group = group_name(session_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"event": self.connected_event, "reason": "connected"})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def session_event(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_member(self, user, session_id) -> bool:
        try:
            return self.model.objects.filter(
                pk=session_id, users=user, **self.extra_filters
            ).exists()
        except (ValueError, ValidationError):
            return False
