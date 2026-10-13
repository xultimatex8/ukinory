from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.enums import SessionStatus, SwipeSessionType
from apps.common.models import Session
from apps.swipe_sessions.constants import PAIRED_MAX_PARTICIPANTS
from apps.swipe_sessions.exceptions import PairedSessionClosedError, PairedSessionFullError
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.realtime import notify_session
from apps.swipe_sessions.services.session import lock_session


@transaction.atomic
def accept_paired_swipe_invite(invite, user) -> SwipeSession:
    if invite.session_id is None:
        raise PairedSessionClosedError

    try:
        session = lock_session(invite.session_id)
    except (Session.DoesNotExist, SwipeSession.DoesNotExist) as exc:
        raise PairedSessionClosedError from exc

    if session.type != SwipeSessionType.PAIRED or session.status == SessionStatus.FINISHED:
        raise PairedSessionClosedError
    if session.status != SessionStatus.WAITING or session.users.count() >= PAIRED_MAX_PARTICIPANTS:
        raise PairedSessionFullError

    session.users.add(user)
    session.last_seen_at = timezone.now()
    session.save(update_fields=["last_seen_at"])

    transaction.on_commit(
        lambda: notify_session(session.pk, event="session.updated", reason="partner_joined")
    )
    return session