from django.urls import path

from apps.library.views import (
    LibraryStatsView,
    RateMovieView,
    UserHasFilmDataView,
    WatchlistExportView,
)

urlpatterns = [
    path("has-film-data/", UserHasFilmDataView.as_view(), name="user-has-film-data",),
    path("stats/", LibraryStatsView.as_view(), name="library-stats",),
    path("movies/<int:tmdb_id>/rating/", RateMovieView.as_view(), name="rate-movie",),
    path("watchlist/export/", WatchlistExportView.as_view(), name="watchlist-export",),
]
