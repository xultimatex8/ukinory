from __future__ import annotations

from apps.common.enums import SwipeSessionType
from apps.common.exceptions import SessionClosedError
from apps.invites.services.session_invites import join_session_from_invite
from apps.swipe_sessions.models import SwipeSession
from apps.common.realtime import notify_session


def _ensure_paired(session: SwipeSession) -> None:
    if session.type != SwipeSessionType.PAIRED:
        raise SessionClosedError


def accept_paired_swipe_invite(invite, user) -> SwipeSession:
    return join_session_from_invite(
        invite,
        user,
        SwipeSession,
        validate=_ensure_paired,
        notify=lambda session: notify_session(
            session.pk, event="session.updated", reason="partner_joined"
        ),
    )
