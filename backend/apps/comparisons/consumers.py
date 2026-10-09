from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError

from apps.comparisons.models import ComparisonSession
from apps.comparisons.realtime import group_name


class ComparisonRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        room_id = self.scope["url_route"]["kwargs"]["room_id"]

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._is_member(user, room_id):
            await self.close(code=4403)
            return

        self.group = group_name(room_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"event": "room.updated", "reason": "connected"})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def room_event(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_member(self, user, room_id) -> bool:
        try:
            return ComparisonSession.objects.filter(pk=room_id, users=user).exists()
        except (ValueError, ValidationError):
            return False
