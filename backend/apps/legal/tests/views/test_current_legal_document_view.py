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


@pytest.fixture
def current_documents(published_documents):
    return [published_documents.terms_v2, published_documents.privacy_v1]



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

    def test_returns_current_privacy_policy(self, current_documents):
        response = APIClient().get(
            reverse("current-document", kwargs={"doc_type": LegalDocumentType.PRIVACY})
        )

        expected = next(d for d in current_documents if d.type == LegalDocumentType.PRIVACY)
        assert response.status_code == 200
        assert response.data["id"] == str(expected.pk)

    def test_returns_the_newest_version_when_older_ones_exist(self, published_documents):
        response = APIClient().get(
            reverse("current-document", kwargs={"doc_type": LegalDocumentType.TERMS})
        )

        assert response.status_code == 200
        assert response.data["id"] == str(published_documents.terms_v2.pk)
        assert response.data["version"] == "2"

    def test_accepts_mixed_case_document_type(self, current_documents):
        response = APIClient().get(
            reverse("current-document", kwargs={"doc_type": "Privacy"})
        )

        assert response.status_code == 200
        assert response.data["type"] == LegalDocumentType.PRIVACY

    def test_returns_404_when_only_the_other_type_is_published(self, published_documents):
        published_documents.privacy_v1.delete()

        response = APIClient().get(
            reverse("current-document", kwargs={"doc_type": LegalDocumentType.PRIVACY})
        )

        assert response.status_code == 404

    def test_ignores_invalid_credentials(self, current_documents):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = client.get(
            reverse("current-document", kwargs={"doc_type": LegalDocumentType.TERMS})
        )

        assert response.status_code == 200

    def test_rejects_unsupported_methods(self, current_documents):
        response = APIClient().post(
            reverse("current-document", kwargs={"doc_type": LegalDocumentType.TERMS})
        )

        assert response.status_code == 405
