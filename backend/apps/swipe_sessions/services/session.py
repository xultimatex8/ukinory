from __future__ import annotations

from django.db import transaction

from apps.common.enums import SwipeSessionStatus
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.candidate_pool import fill_candidate_pool
from apps.swipe_sessions.services.watchlist_export import export_watchlist_csv
from apps.swipe_sessions.exceptions import NotSessionMemberError, SwipeSessionNotFoundError


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
    session.save(update_fields=["status"])

    fill_candidate_pool(session=session, user=user)

    return session


@transaction.atomic
def end_swipe_session(user, session: SwipeSession) -> SwipeExportSummary:
    if session.status != SwipeSessionStatus.ACTIVE:
        raise ValueError("Swipe session has not started yet.")

    session.status = SwipeSessionStatus.FINISHED
    session.save(update_fields=["status"])

    return export_watchlist_csv(user=user)