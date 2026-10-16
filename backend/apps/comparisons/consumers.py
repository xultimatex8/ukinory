from __future__ import annotations

from apps.common.consumers import BaseSessionConsumer
from apps.comparisons.models import ComparisonSession
from apps.comparisons.realtime import ROOM_UPDATED


class ComparisonRoomConsumer(BaseSessionConsumer):
    model = ComparisonSession
    connected_event = ROOM_UPDATED
