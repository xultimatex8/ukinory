from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.enums import SessionStatus, SessionType, SwipeSessionType
from apps.common.models import Session
from apps.swipe_sessions.constants import PAIRED_MAX_PARTICIPANTS
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.realtime import notify_session
from apps.swipe_sessions.services.candidate_pool import (
    fill_candidate_pool,
    fill_paired_candidate_pool,
)
from apps.swipe_sessions.services.watchlist_export import export_watchlist_csv
from apps.common.exceptions import NotSessionMemberError, PartnerNotJoinedError, SessionFinishedError, SessionNotFoundError

LEAVE_TOKEN_SALT = "swipe_sessions.leave"
LEAVE_TOKEN_MAX_AGE = 60 * 60 * 6

STALE_SESSION_TIMEOUT = timedelta(minutes=2)


def get_user_swipe_session(*, session_id, user) -> SwipeSession:
    try:
        session = SwipeSession.objects.get(pk=session_id)
    except SwipeSession.DoesNotExist as exc:
        raise SessionNotFoundError from exc

    if not session.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    return session


def lock_session(session_id) -> SwipeSession:
    Session.objects.select_for_update().get(pk=session_id)
    return SwipeSession.objects.get(pk=session_id)


@transaction.atomic
def create_swipe_session(user, session_type: str) -> SwipeSession:
    session = SwipeSession.objects.create(type=session_type, session_type=SessionType.SWIPE_SESSION)
    session.users.add(user)

    return session


def _start_paired_session(session: SwipeSession) -> SwipeSession:
    session = lock_session(session.pk)

    if session.status == SessionStatus.ACTIVE:
        return session
    if session.status != SessionStatus.WAITING:
        raise ValueError("Swipe session has already started or finished.")
    if session.users.count() < PAIRED_MAX_PARTICIPANTS:
        raise PartnerNotJoinedError

    fill_paired_candidate_pool(session)

    session.status = SessionStatus.ACTIVE
    session.last_seen_at = timezone.now()
    session.save(update_fields=["status", "last_seen_at"])

    transaction.on_commit(
        lambda: notify_session(session.pk, event="session.updated", reason="started")
    )
    return session


@transaction.atomic
def start_swipe_session(user, session: SwipeSession) -> SwipeSession:
    if session.type == SwipeSessionType.PAIRED:
        return _start_paired_session(session)

    if session.status != SessionStatus.WAITING:
        raise ValueError("Swipe session has already started or finished.")

    session.status = SessionStatus.ACTIVE
    session.last_seen_at = timezone.now()
    session.save(update_fields=["status", "last_seen_at"])

    fill_candidate_pool(session=session, user=user)

    return session


def touch_session(session_id) -> None:
    SwipeSession.objects.filter(pk=session_id).update(last_seen_at=timezone.now())


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
        session = lock_session(session.pk)

        if session.status == SessionStatus.FINISHED:
            return export_watchlist_csv(user=user, session=session)

        return _finish_session(session, export_user=user)

    if session.status != SessionStatus.ACTIVE:
        raise ValueError("Swipe session has not started yet.")

    return _finish_session(session)


@transaction.atomic
def ensure_session_finished(session_id) -> SwipeExportSummary | None:
    try:
        session = SwipeSession.objects.select_for_update().get(pk=session_id)
    except SwipeSession.DoesNotExist:
        return None

    if session.status == SessionStatus.FINISHED:
        return None

    return _finish_session(session)


def _is_stale(session: SwipeSession) -> bool:
    if session.status not in (SessionStatus.WAITING, SessionStatus.ACTIVE):
        return False

    cutoff = timezone.now() - STALE_SESSION_TIMEOUT

    if session.last_seen_at is not None:
        return session.last_seen_at < cutoff

    return session.created_at < cutoff


def ensure_session_active(session) -> None:
    if session.status == SessionStatus.FINISHED:
        raise SessionFinishedError

    if _is_stale(session):
        ensure_session_finished(session.pk)
        raise SessionFinishedError
