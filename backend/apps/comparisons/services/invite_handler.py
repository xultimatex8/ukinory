from __future__ import annotations

from django.db import transaction

from apps.comparisons.models import Comparison


@transaction.atomic
def accept_comparison_invite(invite, user) -> Comparison:
    comparison = Comparison.objects.create()
    comparison.users.add(invite.inviter, user)
    return comparison
