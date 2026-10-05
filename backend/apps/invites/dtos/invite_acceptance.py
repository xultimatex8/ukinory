from dataclasses import dataclass
from typing import Any

from apps.invites.models import Invite


@dataclass(frozen=True, slots=True)
class InviteAcceptance:
    invite: Invite
    target: Any
