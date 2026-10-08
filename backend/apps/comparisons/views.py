from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)
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
    touch_room,
)
from apps.invites.exceptions import TooManyPendingInvitesError
from apps.invites.serializers import InviteSerializer
from apps.common.enums import GenerationStatus


def _too_many_invites() -> Response:
    return Response(
        {"detail": "You have too many pending invites."},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


class ComparisonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_comparisons(request.user)
        return Response(ComparisonSummarySerializer(qs, many=True).data)


class ComparisonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, comparison_id):
        try:
            result = get_comparison_result(
                user=request.user,
                comparison_id=comparison_id,
            )
        except ComparisonNotFoundError:
            return Response(
                {"detail": "Comparison not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotComparisonMemberError:
            return Response(
                {"detail": "You are not part of this comparison."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InsufficientDataError as exc:
            return Response(
                {"detail": str(exc) or "Not enough data to compare."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        payload = attach_tmdb_metadata(serialize_result(result))
        return Response(attach_participants(payload, result.comparison, request.user))


class RoomCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            room, invite = create_room(request.user)
        except TooManyPendingInvitesError:
            return _too_many_invites()

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
        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )
        touch_room(room.pk)

        return Response(build_room_state(room, request.user))


class RoomLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, room_id):
        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )
        leave_room(
            room=room,
            user=request.user,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class RoomInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )

        try:
            invite = regenerate_invite(
                user=request.user,
                room=room,
            )
        except TooManyPendingInvitesError:
            return _too_many_invites()

        return Response(
            InviteSerializer(invite).data,
            status=status.HTTP_201_CREATED,
        )


class RoomGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )

        request_generation(room=room)

        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )

        return Response(build_room_state(room, request.user))


class RoomResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_user_room(
            room_id=room_id,
            user=request.user,
        )
        comparison = getattr(room, "comparison", None)

        if (
            comparison is None
            or comparison.generation_status != GenerationStatus.READY
        ):
            return Response(
                {
                    "detail": "The comparison is not ready yet.",
                    "generation_status": (
                        comparison.generation_status
                        if comparison
                        else None
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            result = get_comparison_result(
                user=request.user,
                comparison_id=comparison.pk,
            )
        except InsufficientDataError as exc:
            return Response(
                {"detail": str(exc) or "Not enough data to compare."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        payload = attach_tmdb_metadata(serialize_result(result))
        return Response(attach_participants(payload, result.comparison, request.user))
