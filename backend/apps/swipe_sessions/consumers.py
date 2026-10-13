from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError

from apps.common.enums import SwipeSessionType
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.realtime import group_name


class PairedSwipeConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        session_id = self.scope["url_route"]["kwargs"]["session_id"]

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._is_member(user, session_id):
            await self.close(code=4403)
            return

        self.group = group_name(session_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"event": "session.updated", "reason": "connected"})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def session_event(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_member(self, user, session_id) -> bool:
        try:
            return SwipeSession.objects.filter(
                pk=session_id, users=user, type=SwipeSessionType.PAIRED
            ).exists()
        except (ValueError, ValidationError):
            return False
