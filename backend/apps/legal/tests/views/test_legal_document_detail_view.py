from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.legal.models import LegalDocument, LegalDocumentType


@pytest.mark.django_db
class TestLegalDocumentDetailView:
    def test_returns_document_by_id(self):
        document = LegalDocument.objects.create(
            type=LegalDocumentType.TERMS,
            version="1.0",
            content="Terms and conditions",
        )

        client = APIClient()

        response = client.get(
            reverse(
                "document-detail",
                kwargs={"pk": str(document.pk)},
            )
        )

        assert response.status_code == 200
        assert response.data["id"] == str(document.pk)
        assert response.data["type"] == LegalDocumentType.TERMS
        assert response.data["version"] == "1.0"
        assert response.data["content"] == "Terms and conditions"

    def test_returns_404_for_nonexistent_document(self):
        client = APIClient()

        response = client.get(
            reverse(
                "document-detail",
                kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
            )
        )

        assert response.status_code == 404

    def test_returns_404_for_future_document(self):
        document = LegalDocument.objects.create(
            type=LegalDocumentType.TERMS,
            version="2.0",
            content="Future terms",
            effective_at=timezone.now() + timedelta(days=1),
        )

        client = APIClient()

        response = client.get(
            reverse(
                "document-detail",
                kwargs={"pk": str(document.pk)},
            )
        )

        assert response.status_code == 404
