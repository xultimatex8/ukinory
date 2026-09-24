from django.db import transaction

from apps.legal.models import UserLegalAcceptance
from apps.legal.services.acceptance_validation import validate_acceptance
from apps.legal.services.record_acceptance import record_acceptance

@transaction.atomic
def accept_current_documents(user, documents) -> list[UserLegalAcceptance]:
    validate_acceptance(documents)
    return record_acceptance(user, documents)
