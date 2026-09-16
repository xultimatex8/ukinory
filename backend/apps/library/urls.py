from django.urls import path

from apps.library.views import UserHasFilmDataView

urlpatterns = [
    path("has-film-data/", UserHasFilmDataView.as_view(), name="user-has-film-data",)
]
