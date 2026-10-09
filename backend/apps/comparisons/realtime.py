from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def group_name(room_id) -> str:
    return f"comparison_room_{room_id}"


def notify_room(room_id, **payload) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    layer = get_channel_layer()
    if layer is None:
        return

    try:
        async_to_sync(layer.group_send)(
            group_name(room_id),
            {"type": "room.event", "payload": {"event": "room.updated", **payload}},
        )
    except Exception as exc:
        logger.warning("Could not notify room %s: %s", room_id, exc)
