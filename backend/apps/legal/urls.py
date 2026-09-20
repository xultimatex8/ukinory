from django.urls import path

from apps.legal.views import CurrentLegalDocumentView, CurrentLegalDocumentsView, LegalDocumentDetailView, MyLegalAcceptancesView


urlpatterns = [
    path("documents/", CurrentLegalDocumentsView.as_view(), name="current-documents"),
    path("documents/by-id/<str:pk>/", LegalDocumentDetailView.as_view(), name="document-detail"),
    path("documents/<str:doc_type>/", CurrentLegalDocumentView.as_view(), name="current-document"),
    path("acceptances/", MyLegalAcceptancesView.as_view(), name="my-acceptances"),
]
