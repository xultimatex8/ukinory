from django.db import transaction
from django.utils import timezone

from apps.legal.exceptions import LegalAcceptanceError
from apps.legal.models import UserLegalAcceptance


@transaction.atomic
def record_acceptance(user, documents) -> list[UserLegalAcceptance]:
    if user.is_guest:
        raise LegalAcceptanceError("Guest sessions do not record legal acceptance.")

    now = timezone.now()
    UserLegalAcceptance.objects.bulk_create(
        [UserLegalAcceptance(user=user, document=d, accepted_at=now) for d in documents],
        ignore_conflicts=True,
    )
    
    return list(
        UserLegalAcceptance.objects.filter(user=user, document__in=documents).select_related("document")
    )
