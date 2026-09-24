from apps.common.enums import LegalDocumentType
from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailableError
from apps.legal.models import LegalDocument


def get_current_documents(at=None) -> list[LegalDocument]:
    order = {value: index for index, value in enumerate(LegalDocumentType.values)}
    return sorted(LegalDocument.objects.current(at), key=lambda document: order[document.type])


def validate_acceptance(documents) -> list[LegalDocument]:
    current = get_current_documents()

    published_types = {d.type for d in current}
    missing = set(LegalDocumentType.values) - published_types
    if missing:
        raise LegalDocumentsUnavailableError(
            f"No effective version published for: {', '.join(sorted(missing))}"
        )

    if {d.pk for d in documents} != {d.pk for d in current}:
        raise LegalAcceptanceError(
            "You must accept the current Terms and Conditions and Privacy Policy."
        )
    
    return current
