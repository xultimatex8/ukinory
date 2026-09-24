from django.urls import path

from apps.swipe_sessions.views import (
    SwipeSessionCandidateJustificationView,
    SwipeSessionDetailView,
    SwipeSessionEndView,
    SwipeSessionHeartbeatView,
    SwipeSessionListCreateView,
    SwipeSessionRecommendationView,
    SwipeSessionStartView,
    SwipeSessionSwipeView,
)


urlpatterns = [
    path("", SwipeSessionListCreateView.as_view(), name="swipe-session-list-create"),
    path("<uuid:pk>/", SwipeSessionDetailView.as_view(), name="swipe-session-detail"),
    path("<uuid:pk>/start/", SwipeSessionStartView.as_view(), name="swipe-session-start"),
    path("<uuid:pk>/end/", SwipeSessionEndView.as_view(), name="swipe-session-watchlist-export"),
    path("<uuid:pk>/heartbeat/", SwipeSessionHeartbeatView.as_view(), name="swipe-session-heartbeat"),
    path("<uuid:pk>/recommendation/", SwipeSessionRecommendationView.as_view(), name="swipe-session-recommendation"),
    path("<uuid:pk>/candidates/<uuid:candidate_id>/justification/", SwipeSessionCandidateJustificationView.as_view(), name="swipe-session-candidate-justification"),
    path("<uuid:pk>/swipe/", SwipeSessionSwipeView.as_view(), name="swipe-session-swipe"),
]
