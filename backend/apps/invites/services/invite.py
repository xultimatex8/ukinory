from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.common.enums import InviteStatus
from apps.invites import registry
from apps.invites.models import Invite
from apps.invites.dtos.invite_acceptance import InviteAcceptance
from apps.invites.exceptions import InviteAlreadyAcceptedError, InviteExpiredError, InviteNotFoundError, OwnInviteError, TooManyPendingInvitesError

INVITE_TTL = timedelta(minutes=5)
CODE_BYTES = 32
MAX_PENDING_INVITES_PER_USER = 20


def create_invite(*, user, invite_type: str) -> Invite:
    pending = Invite.objects.filter(
        inviter=user, status=InviteStatus.PENDING,
        expires_at__gt=timezone.now(),
    ).count()
    if pending >= MAX_PENDING_INVITES_PER_USER:
        raise TooManyPendingInvitesError
    
    return Invite.objects.create(
        inviter=user, type=invite_type,
        code=secrets.token_urlsafe(CODE_BYTES),
        expires_at=timezone.now() + INVITE_TTL,
    )


@transaction.atomic
def accept_invite(*, user, code: str) -> InviteAcceptance:
    try:
        invite = (
            Invite.objects.select_for_update(of=("self",))
            .select_related("inviter").get(code=code)
        )
    except Invite.DoesNotExist as exc:
        raise InviteNotFoundError from exc

    if invite.inviter_id == user.pk:
        raise OwnInviteError
    if invite.status == InviteStatus.ACCEPTED:
        raise InviteAlreadyAcceptedError
    if invite.is_expired:
        raise InviteExpiredError

    handler = registry.get_acceptance_handler(invite.type)
    target = handler(invite, user)
    invite.status = InviteStatus.ACCEPTED
    invite.accepted_by = user
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["status", "accepted_by", "accepted_at"])

    return InviteAcceptance(invite=invite, target=target)


def expire_stale_invites() -> int:
    return Invite.objects.filter(
        status=InviteStatus.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=InviteStatus.EXPIRED)
