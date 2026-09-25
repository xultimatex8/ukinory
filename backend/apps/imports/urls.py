from django.urls import path

from apps.imports.views import LetterboxdImportStatusView, LetterboxdImportView

urlpatterns = [
    path(
        "letterboxd/",
        LetterboxdImportView.as_view(),
        name="import-letterboxd",
    ),
    path(
        "letterboxd/<int:job_id>/status/",
        LetterboxdImportStatusView.as_view(),
        name="letterboxd-import-status",
    ),
]