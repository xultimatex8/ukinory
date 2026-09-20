from rest_framework.exceptions import APIException


class LegalDocumentImmutableError(Exception):
    """Raised when trying to modify a LegalDocument that is already persisted."""


class LegalAcceptanceError(Exception):
    """The submitted acceptance is invalid (client-side problem)."""


class LegalDocumentsUnavailableError(Exception):
    """No effective version exists for a required document type (server-side problem)."""


class LegalDocumentsUnavailable(APIException):
    status_code = 503
    default_detail = "Legal documents are temporarily unavailable."
    default_code = "legal_documents_unavailable"
