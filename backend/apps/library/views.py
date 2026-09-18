from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.library.models import Rating


class UserHasFilmDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_film_data = (
            Rating.objects.filter(user=request.user).exists()
        )

        return Response(has_film_data)
