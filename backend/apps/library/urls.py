from django.urls import path

from apps.library.views import UserHasFilmDataView, LibraryStatsView

urlpatterns = [
    path("has-film-data/", UserHasFilmDataView.as_view(), name="user-has-film-data",),
    path("stats/", LibraryStatsView.as_view(), name="library-stats",)
]
