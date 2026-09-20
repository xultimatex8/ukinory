from datetime import timedelta

from django.utils import timezone

from apps.common.enums import LegalDocumentType
from apps.legal.models import LegalDocument


def make_document(doc_type, version, days_ago=1, content="text"):
    return LegalDocument.objects.create(
        type=doc_type,
        version=version,
        content=content,
        effective_at=timezone.now() - timedelta(days=days_ago),
    )


def create_current_documents():
    return [
        make_document(LegalDocumentType.TERMS, "1"),
        make_document(LegalDocumentType.PRIVACY, "1"),
    ]
