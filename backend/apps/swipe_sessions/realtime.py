from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def group_name(session_id) -> str:
    return f"swipe_session_{session_id}"


def notify_session(session_id, **payload) -> None:
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
            group_name(session_id),
            {"type": "session.event", "payload": payload},
        )
    except Exception as exc:
        logger.warning("Could not notify swipe session %s: %s", session_id, exc)
