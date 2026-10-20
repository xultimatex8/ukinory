from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.legal.models import LegalDocument, LegalDocumentType
from types import SimpleNamespace
from apps.legal.tests.factories import make_document


@pytest.fixture
def published_documents(db):
    return SimpleNamespace(
        terms_v1=make_document(LegalDocumentType.TERMS, "1", days_ago=30),
        terms_v2=make_document(LegalDocumentType.TERMS, "2", days_ago=5),
        privacy_v1=make_document(LegalDocumentType.PRIVACY, "1", days_ago=30),
    )



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

    def test_returns_superseded_versions_that_are_already_effective(
        self, published_documents
    ):
        old = published_documents.terms_v1

        response = APIClient().get(
            reverse("document-detail", kwargs={"pk": str(old.pk)})
        )

        assert response.status_code == 200
        assert response.data["id"] == str(old.pk)
        assert response.data["version"] == "1"

    def test_ignores_invalid_credentials(self, published_documents):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = client.get(
            reverse(
                "document-detail",
                kwargs={"pk": str(published_documents.terms_v2.pk)},
            )
        )

        assert response.status_code == 200

    def test_rejects_unsupported_methods(self, published_documents):
        response = APIClient().post(
            reverse(
                "document-detail",
                kwargs={"pk": str(published_documents.terms_v2.pk)},
            )
        )

        assert response.status_code == 405
