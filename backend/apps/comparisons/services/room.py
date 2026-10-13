from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.enums import (
    GenerationStatus,
    InviteType,
    SessionStatus,
    SessionType,
)
from apps.common.exceptions import NotSessionMemberError, SessionClosedError
from apps.common.services.sessions import (
    StaleOutcome,
    activate_session,
    close_stale_session,
    close_stale_sessions,
    get_user_session,
    is_stale,
    touch_session,
)
from apps.comparisons.exceptions import InsufficientDataError
from apps.comparisons.models import Comparison, ComparisonSession
from apps.comparisons.realtime import notify_room
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite
from apps.invites.services.session_invites import regenerate_session_invite
from apps.library.models import Rating

logger = logging.getLogger(__name__)

RUNNING_TIMEOUT = timedelta(minutes=2)


def get_user_room(*, room_id, user) -> ComparisonSession:
    return get_user_session(
        ComparisonSession,
        session_id=room_id,
        user=user,
        queryset=ComparisonSession.objects.select_related("comparison").prefetch_related("users"),
    )


def _comparison_of(room: ComparisonSession) -> Comparison | None:
    return getattr(room, "comparison", None)


def heartbeat_room(room: ComparisonSession) -> None:
    if is_stale(room):
        outcome = close_stale_session(room.pk)
        if outcome is StaleOutcome.DELETED:
            raise SessionClosedError
        if outcome is StaleOutcome.FINISHED:
            room.status = SessionStatus.FINISHED
            return
    touch_session(room.pk)


def build_room_state(room: ComparisonSession, user) -> dict:
    users = list(room.users.all())
    comparison = _comparison_of(room)
    with_data = set(
        Rating.objects.filter(user__in=users).values_list("user_id", flat=True).distinct()
    )
    partner = next((u for u in users if u.pk != user.pk), None)

    return {
        "id": str(room.pk),
        "status": room.status,
        "participants": len(users),
        "partner_joined": partner is not None,
        "comparison_id": str(comparison.pk) if comparison else None,
        "generation_status": comparison.generation_status if comparison else None,
        "you_have_data": user.pk in with_data,
        "partner_has_data": (partner.pk in with_data) if partner else None,
    }


@transaction.atomic
def create_room(user) -> tuple[ComparisonSession, Invite]:
    room = ComparisonSession.objects.create(
        session_type=SessionType.COMPARISON_SESSION,
        last_seen_at=timezone.now(),
    )
    room.users.add(user)
    invite = create_invite(user=user, invite_type=InviteType.COMPARISON, session=room)
    return room, invite


def regenerate_invite(*, user, room: ComparisonSession) -> Invite:
    return regenerate_session_invite(
        user=user, session=room, invite_type=InviteType.COMPARISON
    )


def _ensure_comparison(room: ComparisonSession) -> None:
    Comparison.objects.get_or_create(session=room)


def request_generation(*, room: ComparisonSession) -> str:
    activate_session(ComparisonSession, room.pk, prepare=_ensure_comparison)
    comparison = Comparison.objects.get(session_id=room.pk)
    return run_generation(comparison.pk)


def _is_running(c: Comparison) -> bool:
    return (
        c.generation_status == GenerationStatus.RUNNING
        and c.generation_started_at is not None
        and timezone.now() - c.generation_started_at < RUNNING_TIMEOUT
    )


def run_generation(comparison_id) -> str:
    from apps.comparisons.services.comparison import get_comparison_result

    with transaction.atomic():
        c = (
            Comparison.objects.select_for_update(of=("self",))
            .select_related("session")
            .get(pk=comparison_id)
        )
        if c.generation_status == GenerationStatus.READY or _is_running(c):
            return c.generation_status
        c.generation_status = GenerationStatus.RUNNING
        c.generation_started_at = timezone.now()
        c.save(update_fields=["generation_status", "generation_started_at"])

    notify_room(c.session_id, reason="generation_started")

    users = list(c.session.users.all())
    try:
        get_comparison_result(user=users[0], comparison_id=c.pk)
        final = GenerationStatus.READY
    except InsufficientDataError:
        final = GenerationStatus.NEEDS_DATA
    except Exception:
        logger.exception("Comparison %s generation failed", comparison_id)
        final = GenerationStatus.FAILED

    Comparison.objects.filter(pk=c.pk).update(generation_status=final)
    notify_room(c.session_id, reason="generation_finished")
    return final


def close_stale_rooms() -> int:
    return close_stale_sessions(ComparisonSession)


@transaction.atomic
def leave_room(*, room: ComparisonSession, user) -> None:
    if room.status == SessionStatus.FINISHED:
        return

    if not room.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    if room.status == SessionStatus.WAITING:
        room.users.remove(user)
        if not room.users.exists():
            room.delete()
        return

    comparison = Comparison.objects.filter(session=room).first()
    room.users.remove(user)

    if (
        comparison is not None
        and comparison.generation_status
        in {GenerationStatus.PENDING, GenerationStatus.NEEDS_DATA}
    ):
        comparison.delete()
        room.status = SessionStatus.WAITING
    else:
        room.status = SessionStatus.FINISHED

    room.save(update_fields=["status"])
