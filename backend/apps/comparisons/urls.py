from django.urls import path

from apps.comparisons.views import (
    ComparisonDetailView,
    ComparisonListView,
    RoomCreateView,
    RoomDetailView,
    RoomGenerateView,
    RoomInviteView,
    RoomLeaveView,
    RoomResultView,
)


urlpatterns = [
    path("", ComparisonListView.as_view(), name="comparison-list"),
    path("comparison-rooms/", RoomCreateView.as_view(), name="room-create"),
    path("comparison-rooms/<uuid:room_id>/", RoomDetailView.as_view(), name="room-detail"),
    path("comparison-rooms/<uuid:room_id>/invite/", RoomInviteView.as_view(), name="room-invite"),
    path("comparison-rooms/<uuid:room_id>/leave/", RoomLeaveView.as_view(), name="room-leave"),
    path("<uuid:room_id>/generate/", RoomGenerateView.as_view(), name="room-generate"),
    path("<uuid:room_id>/result/", RoomResultView.as_view(), name="room-result"),
    path("<str:comparison_id>/", ComparisonDetailView.as_view(), name="comparison-detail"),
]
