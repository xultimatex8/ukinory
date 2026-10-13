from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.enums import SessionStatus, SessionType, SwipeSessionType
from apps.common.exceptions import InvalidSessionStateError
from apps.common.services.sessions import (
    StaleOutcome,
    activate_session,
    close_stale_sessions,
    get_user_session,
    lock_session,
)
from apps.common.services.sessions import ensure_session_active as _ensure_session_active
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.realtime import notify_session
from apps.swipe_sessions.services.candidate_pool import (
    fill_candidate_pool,
    fill_paired_candidate_pool,
)
from apps.swipe_sessions.services.watchlist_export import export_watchlist_csv

LEAVE_TOKEN_SALT = "swipe_sessions.leave"
LEAVE_TOKEN_MAX_AGE = 60 * 60 * 6


def get_user_swipe_session(*, session_id, user) -> SwipeSession:
    return get_user_session(SwipeSession, session_id=session_id, user=user)


def _notify_closed(session_id, outcome: StaleOutcome) -> None:
    if outcome is StaleOutcome.FINISHED:
        notify_session(session_id, event="session.updated", reason="ended")


def ensure_session_active(session) -> None:
    _ensure_session_active(session, on_closed=_notify_closed)


def close_stale_swipe_sessions() -> int:
    return close_stale_sessions(SwipeSession, on_closed=_notify_closed)


@transaction.atomic
def create_swipe_session(user, session_type: str) -> SwipeSession:
    session = SwipeSession.objects.create(type=session_type, session_type=SessionType.SWIPE_SESSION)
    session.users.add(user)

    return session


def _start_paired_session(session: SwipeSession) -> SwipeSession:
    return activate_session(
        SwipeSession,
        session.pk,
        prepare=fill_paired_candidate_pool,
        notify=lambda s: notify_session(
            s.pk, event="session.updated", reason="started"
        ),
    )


@transaction.atomic
def start_swipe_session(user, session: SwipeSession) -> SwipeSession:
    if session.type == SwipeSessionType.PAIRED:
        return _start_paired_session(session)

    if session.status != SessionStatus.WAITING:
        raise InvalidSessionStateError("Swipe session has already started or finished.")

    session.status = SessionStatus.ACTIVE
    session.last_seen_at = timezone.now()
    session.save(update_fields=["status", "last_seen_at"])

    fill_candidate_pool(session=session, user=user)

    return session


def _finish_session(session: SwipeSession, export_user=None) -> SwipeExportSummary | None:
    session.status = SessionStatus.FINISHED
    session.save(update_fields=["status"])

    if session.type == SwipeSessionType.PAIRED:
        transaction.on_commit(
            lambda: notify_session(session.pk, event="session.updated", reason="ended")
        )

    user = export_user or session.users.first()
    if user is None:
        return None

    return export_watchlist_csv(user=user, session=session)


@transaction.atomic
def end_swipe_session(user, session: SwipeSession) -> SwipeExportSummary:
    if session.type == SwipeSessionType.PAIRED:
        session = lock_session(SwipeSession, session.pk)

        if session.status == SessionStatus.FINISHED:
            return export_watchlist_csv(user=user, session=session)

        return _finish_session(session, export_user=user)

    if session.status != SessionStatus.ACTIVE:
        raise InvalidSessionStateError("Swipe session has not started yet.")

    return _finish_session(session)
