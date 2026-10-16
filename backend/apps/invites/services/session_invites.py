from __future__ import annotations

from typing import Callable, Optional

from django.db import transaction
from django.utils import timezone

from apps.common.enums import InviteStatus, SessionStatus
from apps.common.exceptions import (
    SessionClosedError,
    SessionFullError,
    SessionNotFoundError,
)
from apps.common.services.sessions import MAX_PARTICIPANTS, lock_session
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite


@transaction.atomic
def join_session_from_invite(
    invite: Invite,
    user,
    model,
    *,
    validate: Optional[Callable] = None,
    notify: Optional[Callable] = None,
):
    if invite.session_id is None:
        raise SessionNotFoundError

    session = lock_session(model, invite.session_id)

    if validate is not None:
        validate(session)
    if session.status == SessionStatus.FINISHED:
        raise SessionClosedError
    if session.status != SessionStatus.WAITING or session.users.count() >= MAX_PARTICIPANTS:
        raise SessionFullError

    session.users.add(user)
    session.last_seen_at = timezone.now()
    session.save(update_fields=["last_seen_at"])

    if notify is not None:
        transaction.on_commit(lambda: notify(session))
    return session


@transaction.atomic
def regenerate_session_invite(*, user, session, invite_type: str) -> Invite:
    if session.status != SessionStatus.WAITING:
        raise SessionClosedError
    if session.users.count() >= MAX_PARTICIPANTS:
        raise SessionFullError

    Invite.objects.filter(
        inviter=user,
        session_id=session.pk,
        status=InviteStatus.PENDING,
    ).update(status=InviteStatus.EXPIRED)

    return create_invite(user=user, invite_type=invite_type, session=session)
