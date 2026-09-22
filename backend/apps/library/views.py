from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.library.models import Rating
from apps.library.serializers import RateMovieSerializer
from apps.library.services.ratings import rate_movie
from apps.movies.models import Movie


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


class RateMovieView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request, tmdb_id):
        try:
            movie = Movie.objects.get(tmdb_id=tmdb_id)
        except Movie.DoesNotExist:
            return Response(
                {"detail": "Movie not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
 
        serializer = RateMovieSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        rate_movie(
            user=request.user,
            movie=movie,
            rating=serializer.validated_data.get("rating"),
            liked=serializer.validated_data.get("liked", False),
            watched_date=serializer.validated_data.get("watched_date"),
        )
 
        return Response(status=status.HTTP_200_OK)
