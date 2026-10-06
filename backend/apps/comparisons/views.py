from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)
from apps.comparisons.serializers import (
    ComparisonSummarySerializer,
    serialize_result,
)
from apps.comparisons.services.comparison import (
    get_comparison_result,
    list_comparisons,
)


class ComparisonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_comparisons(request.user)
        return Response(ComparisonSummarySerializer(qs, many=True).data)


class ComparisonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, comparison_id):
        try:
            result = get_comparison_result(
                user=request.user,
                comparison_id=comparison_id,
            )
        except ComparisonNotFoundError:
            return Response(
                {"detail": "Comparison not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotComparisonMemberError:
            return Response(
                {"detail": "You are not part of this comparison."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InsufficientDataError as exc:
            return Response(
                {"detail": str(exc) or "Not enough data to compare."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(serialize_result(result))
