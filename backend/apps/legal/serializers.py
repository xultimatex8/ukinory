from rest_framework import serializers

from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailable, LegalDocumentsUnavailableError

from .models import LegalDocument, UserLegalAcceptance
from apps.legal.services.acceptance_validation import validate_acceptance


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = ["id", "type", "version", "content", "effective_at"]
        read_only_fields = fields


class LegalDocumentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = ["id", "type", "version", "effective_at"]
        read_only_fields = fields


class UserLegalAcceptanceSerializer(serializers.ModelSerializer):
    document = LegalDocumentSummarySerializer(read_only=True)

    class Meta:
        model = UserLegalAcceptance
        fields = ["document", "accepted_at"]
        read_only_fields = fields


class LegalAcceptanceMixin(serializers.Serializer):
    accepted_documents = serializers.PrimaryKeyRelatedField(
        queryset=LegalDocument.objects.all(),
        many=True,
        allow_empty=False,
        write_only=True,
    )

    def validate_accepted_documents(self, documents):
        try:
            validate_acceptance(documents)
        except LegalAcceptanceError as exc:
            raise serializers.ValidationError(str(exc))
        except LegalDocumentsUnavailableError:
            raise LegalDocumentsUnavailable()
        return documents
