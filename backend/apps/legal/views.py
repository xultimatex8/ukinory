from django.http import Http404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.legal.services.acceptance_validation import get_current_documents

from .models import LegalDocument, LegalDocumentType, UserLegalAcceptance
from .serializers import LegalDocumentSerializer, UserLegalAcceptanceSerializer


class PublicLegalMixin:
    authentication_classes: list = []
    permission_classes = [AllowAny]


class CurrentLegalDocumentsView(PublicLegalMixin, APIView):
    def get(self, request):
        return Response(LegalDocumentSerializer(get_current_documents(), many=True).data)


class CurrentLegalDocumentView(PublicLegalMixin, APIView):
    def get(self, request, doc_type):
        doc_type = doc_type.upper()
        if doc_type not in LegalDocumentType.values:
            raise Http404
        document = next((d for d in get_current_documents() if d.type == doc_type), None)
        if document is None:
            raise Http404
        return Response(LegalDocumentSerializer(document).data)


class LegalDocumentDetailView(PublicLegalMixin, RetrieveAPIView):
    serializer_class = LegalDocumentSerializer

    def get_queryset(self):
        return LegalDocument.objects.effective()


class MyLegalAcceptancesView(ListAPIView):
    serializer_class = UserLegalAcceptanceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return UserLegalAcceptance.objects.filter(user=self.request.user).select_related("document")
