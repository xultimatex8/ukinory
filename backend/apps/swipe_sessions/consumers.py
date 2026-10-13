from __future__ import annotations

from apps.common.consumers import BaseSessionConsumer
from apps.common.enums import SwipeSessionType
from apps.swipe_sessions.models import SwipeSession


class PairedSwipeConsumer(BaseSessionConsumer):
    model = SwipeSession
    extra_filters = {"type": SwipeSessionType.PAIRED}
    connected_event = "session.updated"
