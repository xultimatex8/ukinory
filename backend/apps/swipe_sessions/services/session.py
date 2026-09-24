from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.enums import SwipeSessionStatus
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.candidate_pool import fill_candidate_pool
from apps.swipe_sessions.services.watchlist_export import export_watchlist_csv
from apps.swipe_sessions.exceptions import NotSessionMemberError, SwipeSessionFinishedError, SwipeSessionNotFoundError

LEAVE_TOKEN_SALT = "swipe_sessions.leave"
LEAVE_TOKEN_MAX_AGE = 60 * 60 * 6

STALE_SESSION_TIMEOUT = timedelta(minutes=2)


def get_user_swipe_session(*, session_id, user) -> SwipeSession:
    try:
        session = SwipeSession.objects.get(pk=session_id)
    except SwipeSession.DoesNotExist as exc:
        raise SwipeSessionNotFoundError from exc

    if not session.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    return session


@transaction.atomic
def create_swipe_session(user, session_type: str) -> SwipeSession:
    session = SwipeSession.objects.create(type=session_type)
    session.users.add(user)

    return session


@transaction.atomic
def start_swipe_session(user, session: SwipeSession) -> SwipeSession:
    if session.status != SwipeSessionStatus.WAITING:
        raise ValueError("Swipe session has already started or finished.")

    session.status = SwipeSessionStatus.ACTIVE
    session.last_seen_at = timezone.now()
    session.save(update_fields=["status", "last_seen_at"])

    fill_candidate_pool(session=session, user=user)

    return session


def touch_session(session_id) -> None:
    SwipeSession.objects.filter(pk=session_id).update(last_seen_at=timezone.now())


def _finish_session(session: SwipeSession) -> SwipeExportSummary | None:
    session.status = SwipeSessionStatus.FINISHED
    session.save(update_fields=["status"])

    user = session.users.first()
    if user is None:
        return None

    return export_watchlist_csv(user=user, session=session)


@transaction.atomic
def end_swipe_session(user, session: SwipeSession) -> SwipeExportSummary:
    if session.status != SwipeSessionStatus.ACTIVE:
        raise ValueError("Swipe session has not started yet.")

    return _finish_session(session)


@transaction.atomic
def ensure_session_finished(session_id) -> SwipeExportSummary | None:
    try:
        session = SwipeSession.objects.select_for_update().get(pk=session_id)
    except SwipeSession.DoesNotExist:
        return None

    if session.status == SwipeSessionStatus.FINISHED:
        return None

    return _finish_session(session)


def _is_stale(session: SwipeSession) -> bool:
    if session.status not in (SwipeSessionStatus.WAITING, SwipeSessionStatus.ACTIVE):
        return False

    cutoff = timezone.now() - STALE_SESSION_TIMEOUT

    if session.last_seen_at is not None:
        return session.last_seen_at < cutoff

    return session.created_at < cutoff


def ensure_session_active(session) -> None:
    if session.status == SwipeSessionStatus.FINISHED:
        raise SwipeSessionFinishedError

    if _is_stale(session):
        ensure_session_finished(session.pk)
        raise SwipeSessionFinishedError
