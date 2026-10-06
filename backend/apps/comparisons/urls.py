from django.urls import path

from apps.comparisons.views import ComparisonDetailView, ComparisonListView

urlpatterns = [
    path("", ComparisonListView.as_view(), name="comparison-list"),
    path("<str:comparison_id>/", ComparisonDetailView.as_view(), name="comparison-detail"),
]
