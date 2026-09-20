from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.legal.models import LegalDocument, LegalDocumentType


@pytest.mark.django_db
class TestCurrentLegalDocumentView:
    def test_returns_current_document(self, current_documents):
        client = APIClient()

        response = client.get(
            reverse(
                "current-document",
                kwargs={"doc_type": LegalDocumentType.TERMS},
            )
        )

        expected = next(
            document
            for document in current_documents
            if document.type == LegalDocumentType.TERMS
        )

        assert response.status_code == 200
        assert response.data["type"] == LegalDocumentType.TERMS
        assert response.data["version"] == expected.version

    def test_accepts_lowercase_document_type(self, current_documents):
        client = APIClient()

        response = client.get(
            reverse(
                "current-document",
                kwargs={"doc_type": "terms"},
            )
        )

        assert response.status_code == 200
        assert response.data["type"] == LegalDocumentType.TERMS

    def test_returns_404_for_invalid_document_type(self):
        client = APIClient()

        response = client.get(
            reverse(
                "current-document",
                kwargs={"doc_type": "INVALID"},
            )
        )

        assert response.status_code == 404

    def test_returns_404_when_no_current_document_exists(self):
        client = APIClient()

        response = client.get(
            reverse(
                "current-document",
                kwargs={"doc_type": LegalDocumentType.TERMS},
            )
        )

        assert response.status_code == 404

    def test_returns_404_when_only_future_document_exists(self):
        LegalDocument.objects.create(
            type=LegalDocumentType.TERMS,
            version="2.0",
            content="Future terms",
            effective_at=timezone.now() + timedelta(days=1),
        )

        client = APIClient()

        response = client.get(
            reverse(
                "current-document",
                kwargs={"doc_type": LegalDocumentType.TERMS},
            )
        )

        assert response.status_code == 404
