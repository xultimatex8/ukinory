from rest_framework import serializers

from apps.comparisons.models import Comparison


class ComparisonSummarySerializer(serializers.ModelSerializer):
    user_ids = serializers.SerializerMethodField()

    class Meta:
        model = Comparison
        fields = ["id", "user_ids", "generated_at"]

    def get_user_ids(self, obj):
        return [u.pk for u in obj.users.all()]


def serialize_result(result) -> dict:
    return {
        "id": result.comparison.pk,
        "generated_at": result.comparison.generated_at,
        "metrics": result.metrics,
        "narrative": result.narrative,
        "narrative_available": result.narrative_available,
        "recommendations": result.recommendations,
        "individual_narratives": result.individual
    }
