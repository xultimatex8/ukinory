from django.urls import path

from apps.imports.views import LetterboxdImportView

urlpatterns = [
    path(
        "letterboxd/",
        LetterboxdImportView.as_view(),
        name="import-letterboxd",
    ),
]