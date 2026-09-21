from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.library.models import Rating


class UserHasFilmDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_film_data = Rating.objects.filter(user=request.user).exists()

        return Response(has_film_data)


class LibraryStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ratings = Rating.objects.filter(user=request.user, rating__isnull=False,)

        return Response(
            {
                "rated_total": ratings.count(),
                "rated_with_embedding": ratings.filter(
                    movie__embedding__isnull=False
                ).count(),
            }
        )