from __future__ import annotations

from apps.comparisons.models import ComparisonSession
from apps.comparisons.realtime import notify_room
from apps.invites.services.session_invites import join_session_from_invite


def accept_comparison_invite(invite, user) -> ComparisonSession:
    return join_session_from_invite(
        invite,
        user,
        ComparisonSession,
        notify=lambda room: notify_room(room.pk, reason="partner_joined"),
    )
