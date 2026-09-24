from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.legal.models import LegalDocument
from apps.legal.views import CurrentLegalDocumentsView


pytestmark = pytest.mark.django_db


class TestCurrentLegalDocumentsView:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.view = CurrentLegalDocumentsView.as_view()
        self.url = "/api/legal/documents/"

    def test_returns_current_document_for_each_type(self):
        now = timezone.now()

        terms_old = LegalDocument.objects.create(
            type="TERMS",
            version="1.0",
            content="Old terms",
            effective_at=now - timedelta(days=10),
        )
        terms_current = LegalDocument.objects.create(
            type="TERMS",
            version="2.0",
            content="Current terms",
            effective_at=now - timedelta(days=1),
        )
        privacy_current = LegalDocument.objects.create(
            type="PRIVACY",
            version="1.0",
            content="Current privacy",
            effective_at=now - timedelta(days=2),
        )

        request = self.factory.get(self.url)
        response = self.view(request)

        assert response.status_code == 200
        assert len(response.data) == 2

        returned_ids = {document["id"] for document in response.data}

        assert str(terms_current.id) in returned_ids
        assert str(privacy_current.id) in returned_ids
        assert str(terms_old.id) not in returned_ids

    def test_does_not_return_future_documents(self):
        future_document = LegalDocument.objects.create(
            type="TERMS",
            version="1.0",
            content="Future terms",
            effective_at=timezone.now() + timedelta(days=1),
        )

        request = self.factory.get(self.url)
        response = self.view(request)

        assert response.status_code == 200
        assert response.data == []

    def test_is_accessible_without_authentication(self):
        request = self.factory.get(self.url)

        response = self.view(request)

        assert response.status_code == 200
