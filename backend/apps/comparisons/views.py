from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.enums import GenerationStatus
from apps.comparisons.serializers import (
    ComparisonSummarySerializer,
    serialize_result,
)
from apps.comparisons.services.comparison import (
    attach_participants,
    attach_tmdb_metadata,
    get_comparison_result,
    list_comparisons,
)
from apps.comparisons.services.room import (
    build_room_state,
    create_room,
    get_user_room,
    leave_room,
    regenerate_invite,
    request_generation,
    heartbeat_room,
)
from apps.comparisons.services.watchlist import (
    add_recommendation_to_watchlist,
    attach_watchlist_state,
    export_recommendations_csv,
    remove_recommendation_from_watchlist,
)
from apps.invites.serializers import InviteSerializer


class ComparisonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_comparisons(request.user)
        return Response(ComparisonSummarySerializer(qs, many=True).data)


class ComparisonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, comparison_id):
        result = get_comparison_result(
            user=request.user, comparison_id=comparison_id
        )
        payload = attach_tmdb_metadata(serialize_result(result))
        return Response(attach_participants(payload, result.comparison, request.user))


class RoomCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room, invite = create_room(request.user)
        return Response(
            {
                "room": build_room_state(room, request.user),
                "invite": InviteSerializer(invite).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        heartbeat_room(room)
        return Response(build_room_state(room, request.user))


class RoomLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        leave_room(room=room, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoomInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        invite = regenerate_invite(user=request.user, room=room)
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class RoomGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        request_generation(room=room)
        room = get_user_room(room_id=room_id, user=request.user)
        return Response(build_room_state(room, request.user))


class RoomResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        comparison = getattr(room, "comparison", None)

        if (
            comparison is None
            or comparison.generation_status != GenerationStatus.READY
        ):
            return Response(
                {
                    "detail": "The comparison is not ready yet.",
                    "generation_status": (
                        comparison.generation_status if comparison else None
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        result = get_comparison_result(
            user=request.user, comparison_id=comparison.pk
        )
        payload = attach_tmdb_metadata(serialize_result(result))
        payload = attach_participants(payload, result.comparison, request.user)
        return Response(attach_watchlist_state(payload, request.user))


class RoomWatchlistItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id, movie_id):
        room = get_user_room(room_id=room_id, user=request.user)
        add_recommendation_to_watchlist(
            room=room, user=request.user, movie_id=movie_id
        )
        return Response({"in_watchlist": True}, status=status.HTTP_201_CREATED)

    def delete(self, request, room_id, movie_id):
        room = get_user_room(room_id=room_id, user=request.user)
        remove_recommendation_from_watchlist(
            room=room, user=request.user, movie_id=movie_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoomWatchlistExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_user_room(room_id=room_id, user=request.user)
        content, count = export_recommendations_csv(room=room, user=request.user)

        if count == 0:
            return Response(
                {"detail": "No recommended films in your watchlist yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="ukinory_comparison_watchlist.csv"'
        )
        return response
