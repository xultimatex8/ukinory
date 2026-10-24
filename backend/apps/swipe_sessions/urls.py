from django.urls import path

from apps.swipe_sessions.views import (
    SwipeSessionCandidateJustificationView,
    SwipeSessionDetailView,
    SwipeSessionEndView,
    SwipeSessionHeartbeatView,
    SwipeSessionLeaveView,
    SwipeSessionListCreateView,
    SwipeSessionRecommendationView,
    SwipeSessionStartView,
    SwipeSessionSwipeView,
    PairedSwipeSessionCreateView,
    PairedSwipeSessionInviteView,
    PairedSwipeSessionStateView,
    SwipeSessionMatchesView,
)


urlpatterns = [
    path("", SwipeSessionListCreateView.as_view(), name="swipe-session-list-create"),
    path("paired/", PairedSwipeSessionCreateView.as_view(), name="paired-swipe-session-create"),
    path("<uuid:pk>/", SwipeSessionDetailView.as_view(), name="swipe-session-detail"),
    path("<uuid:pk>/paired/", PairedSwipeSessionStateView.as_view(), name="paired-swipe-session-state"),
    path("<uuid:pk>/invite/", PairedSwipeSessionInviteView.as_view(), name="paired-swipe-session-invite"),
    path("<uuid:pk>/matches/", SwipeSessionMatchesView.as_view(), name="swipe-session-matches"),
    path("<uuid:pk>/start/", SwipeSessionStartView.as_view(), name="swipe-session-start"),
    path("<uuid:pk>/end/", SwipeSessionEndView.as_view(), name="swipe-session-watchlist-export"),
    path("<uuid:pk>/leave/", SwipeSessionLeaveView.as_view(), name="swipe-session-leave"),
    path("<uuid:pk>/heartbeat/", SwipeSessionHeartbeatView.as_view(), name="swipe-session-heartbeat"),
    path("<uuid:pk>/recommendation/", SwipeSessionRecommendationView.as_view(), name="swipe-session-recommendation"),
    path("<uuid:pk>/candidates/<uuid:candidate_id>/justification/", SwipeSessionCandidateJustificationView.as_view(), name="swipe-session-candidate-justification"),
    path("<uuid:pk>/swipe/", SwipeSessionSwipeView.as_view(), name="swipe-session-swipe"),
]
