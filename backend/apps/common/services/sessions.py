from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Any, Callable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.enums import SessionStatus
from apps.common.exceptions import (
    InvalidSessionStateError,
    NotSessionMemberError,
    PartnerNotJoinedError,
    SessionFinishedError,
    SessionNotFoundError,
)
from apps.common.models import Session

STALE_TIMEOUT = timedelta(minutes=2)
MAX_PARTICIPANTS = 2
LIVE_STATUSES = (SessionStatus.WAITING, SessionStatus.ACTIVE)


class StaleOutcome(Enum):
    NOT_STALE = "not_stale"
    FINISHED = "finished"
    DELETED = "deleted"


class LeaveOutcome(Enum):
    ALREADY_FINISHED = "already_finished"
    LEFT = "left"
    DELETED = "deleted"
    FINISHED = "finished"


OnClosed = Callable[[Any, StaleOutcome], None]


def get_user_session(model, *, session_id, user, queryset=None):
    qs = queryset if queryset is not None else model.objects.all()
    try:
        session = qs.get(pk=session_id)
    except (model.DoesNotExist, ValueError, ValidationError) as exc:
        raise SessionNotFoundError from exc

    if all(u.pk != user.pk for u in session.users.all()):
        raise NotSessionMemberError
    return session


def lock_session(model, session_id):
    try:
        Session.objects.select_for_update().get(pk=session_id)
        return model.objects.get(pk=session_id)
    except (Session.DoesNotExist, model.DoesNotExist, ValueError, ValidationError) as exc:
        raise SessionNotFoundError from exc


def touch_session(session_id) -> None:
    Session.objects.filter(pk=session_id).update(last_seen_at=timezone.now())


def _cutoff(now=None):
    return (now or timezone.now()) - STALE_TIMEOUT


def is_stale(session, *, now=None) -> bool:
    if session.status not in LIVE_STATUSES:
        return False
    last_activity = session.last_seen_at or session.created_at
    return last_activity < _cutoff(now)


def stale_sessions(model=Session):
    cutoff = _cutoff()
    return model.objects.filter(status__in=LIVE_STATUSES).filter(
        Q(last_seen_at__lt=cutoff)
        | Q(last_seen_at__isnull=True, created_at__lt=cutoff)
    )


@transaction.atomic
def close_stale_session(
    session_id, *, on_closed: Optional[OnClosed] = None
) -> StaleOutcome:
    try:
        session = Session.objects.select_for_update().get(pk=session_id)
    except Session.DoesNotExist:
        return StaleOutcome.NOT_STALE

    if not is_stale(session):
        return StaleOutcome.NOT_STALE

    if session.status == SessionStatus.WAITING:
        session.delete()
        outcome = StaleOutcome.DELETED
    else:
        session.status = SessionStatus.FINISHED
        session.save(update_fields=["status"])
        outcome = StaleOutcome.FINISHED

    if on_closed is not None:
        transaction.on_commit(lambda: on_closed(session_id, outcome))
    return outcome


def close_stale_sessions(model=Session, *, on_closed: Optional[OnClosed] = None) -> int:
    closed = 0
    for session_id in list(stale_sessions(model).values_list("pk", flat=True)):
        outcome = close_stale_session(session_id, on_closed=on_closed)
        if outcome is not StaleOutcome.NOT_STALE:
            closed += 1
    return closed


def ensure_session_active(session, *, on_closed: Optional[OnClosed] = None) -> None:
    if session.status == SessionStatus.FINISHED:
        raise SessionFinishedError

    if is_stale(session):
        outcome = close_stale_session(session.pk, on_closed=on_closed)
        if outcome is not StaleOutcome.NOT_STALE:
            raise SessionFinishedError


@transaction.atomic
def activate_session(
    model,
    session_id,
    *,
    prepare: Optional[Callable] = None,
    notify: Optional[Callable] = None,
):
    session = lock_session(model, session_id)

    if session.status == SessionStatus.ACTIVE:
        return session
    if session.status != SessionStatus.WAITING:
        raise InvalidSessionStateError("Session has already started or finished.")
    if session.users.count() < MAX_PARTICIPANTS:
        raise PartnerNotJoinedError

    if prepare is not None:
        prepare(session)

    session.status = SessionStatus.ACTIVE
    session.last_seen_at = timezone.now()
    session.save(update_fields=["status", "last_seen_at"])

    if notify is not None:
        transaction.on_commit(lambda: notify(session))
    return session


@transaction.atomic
def leave_session(model, session_id, user) -> LeaveOutcome:
    session = lock_session(model, session_id)

    if session.status == SessionStatus.FINISHED:
        return LeaveOutcome.ALREADY_FINISHED

    if not session.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    if session.status == SessionStatus.WAITING:
        session.users.remove(user)
        if not session.users.exists():
            session.delete()
            return LeaveOutcome.DELETED
        return LeaveOutcome.LEFT

    session.status = SessionStatus.FINISHED
    session.save(update_fields=["status"])
    return LeaveOutcome.FINISHED
