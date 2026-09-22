from django.urls import path

from apps.library.views import RateMovieView, UserHasFilmDataView, LibraryStatsView

urlpatterns = [
    path("has-film-data/", UserHasFilmDataView.as_view(), name="user-has-film-data",),
    path("stats/", LibraryStatsView.as_view(), name="library-stats",),
    path("movies/<int:tmdb_id>/rating/", RateMovieView.as_view(), name="rate-movie",),
]
