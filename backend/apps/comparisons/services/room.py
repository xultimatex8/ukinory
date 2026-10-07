from __future__ import annotations

import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.enums import GenerationStatus, InviteStatus, InviteType, SessionStatus, SessionType
from apps.comparisons.exceptions import (
    InsufficientDataError,
    NotRoomMemberError,
    RoomClosedError,
    RoomFullError,
    RoomNotFoundError,
    RoomNotReadyError,
)
from apps.common.models import Session
from apps.comparisons.models import Comparison, ComparisonSession
from apps.comparisons.realtime import notify_room
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite
from apps.library.models import Rating

logger = logging.getLogger(__name__)

MAX_PARTICIPANTS = 2
WAITING_ROOM_TIMEOUT = timedelta(minutes=30)
RUNNING_TIMEOUT = timedelta(minutes=2)


def get_user_room(*, room_id, user) -> ComparisonSession:
    try:
        room = (
            ComparisonSession.objects.select_related("comparison")
            .prefetch_related("users")
            .get(pk=room_id)
        )
    except (ComparisonSession.DoesNotExist, ValueError, ValidationError) as exc:
        raise RoomNotFoundError from exc

    if user.pk not in {u.pk for u in room.users.all()}:
        raise NotRoomMemberError
    return room


def _comparison_of(room: ComparisonSession) -> Comparison | None:
    return getattr(room, "comparison", None)


def touch_room(room_id) -> None:
    ComparisonSession.objects.filter(pk=room_id).update(last_seen_at=timezone.now())


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


@transaction.atomic
def regenerate_invite(*, user, room: ComparisonSession) -> Invite:
    if room.status != SessionStatus.WAITING:
        raise RoomClosedError

    Invite.objects.filter(
        inviter=user, session_id=room.pk, status=InviteStatus.PENDING
    ).update(status=InviteStatus.EXPIRED)

    return create_invite(user=user, invite_type=InviteType.COMPARISON, session=room)


@transaction.atomic
def join_room_from_invite(invite: Invite, user) -> ComparisonSession:
    if invite.session_id is None:
        raise RoomNotFoundError

    try:
        Session.objects.select_for_update().get(pk=invite.session_id)
        room = ComparisonSession.objects.get(pk=invite.session_id)
    except (Session.DoesNotExist, ComparisonSession.DoesNotExist) as exc:
        raise RoomNotFoundError from exc

    if room.status == SessionStatus.FINISHED:
        raise RoomClosedError
    if room.status != SessionStatus.WAITING or room.users.count() >= MAX_PARTICIPANTS:
        raise RoomFullError

    room.users.add(user)
    room.status = SessionStatus.ACTIVE
    room.last_seen_at = timezone.now()
    room.save(update_fields=["status", "last_seen_at"])

    Comparison.objects.create(session=room)
    transaction.on_commit(lambda: notify_room(room.pk, reason="partner_joined"))
    return room


def request_generation(*, room: ComparisonSession) -> str:
    comparison = _comparison_of(room)
    if room.status != SessionStatus.ACTIVE or comparison is None:
        raise RoomNotReadyError("Both participants must be in the room first.")
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
    cutoff = timezone.now() - WAITING_ROOM_TIMEOUT
    qs = ComparisonSession.objects.filter(status=SessionStatus.WAITING).filter(
        Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True, created_at__lt=cutoff)
    )
    count = qs.count()
    qs.delete()
    return count
