from __future__ import annotations

from apps.comparisons.models import ComparisonSession
from apps.comparisons.services.room import join_room_from_invite


def accept_comparison_invite(invite, user) -> ComparisonSession:
    return join_room_from_invite(invite, user)
