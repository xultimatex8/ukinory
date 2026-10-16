from __future__ import annotations

from apps.common.realtime import notify_session

ROOM_UPDATED = "room.updated"


def notify_room(room_id, **payload) -> None:
    notify_session(room_id, ROOM_UPDATED, **payload)
