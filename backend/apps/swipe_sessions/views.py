from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invites.serializers import InviteSerializer
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.services.tmdb_metadata import (
    fetch_card_metadata_bulk,
    fetch_live_display_metadata,
)
from apps.swipe_sessions.exceptions import JustificationUnavailableError
from apps.swipe_sessions.serializers import (
    CreateSwipeSessionSerializer,
    SwipeSerializer,
    SwipeSessionSerializer,
)
from apps.swipe_sessions.services.justification import get_candidate_justification
from apps.swipe_sessions.services.paired import (
    build_paired_state,
    create_paired_session,
    matched_candidates,
    regenerate_paired_invite,
    require_paired,
)
from apps.swipe_sessions.services.recommendation import (
    get_next_recommendation_for_session,
)
from apps.swipe_sessions.services.session import (
    create_swipe_session,
    end_swipe_session,
    ensure_session_active,
    get_user_swipe_session,
    leave_swipe_session,
    start_swipe_session,
)
from apps.common.services.sessions import touch_session
from apps.swipe_sessions.services.swipe import get_session_candidate, record_swipe


def _get_paired_session(request, pk):
    session = get_user_swipe_session(session_id=pk, user=request.user)
    require_paired(session)
    return session


class SwipeSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateSwipeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = create_swipe_session(
            user=request.user,
            session_type=serializer.validated_data["type"],
        )
        return Response(
            SwipeSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class SwipeSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = get_user_swipe_session(session_id=pk, user=request.user)
        ensure_session_active(session)
        return Response(SwipeSessionSerializer(session).data)


class SwipeSessionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_user_swipe_session(session_id=pk, user=request.user)
        session = start_swipe_session(request.user, session)
        return Response(SwipeSessionSerializer(session).data)


class SwipeSessionRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        result = get_next_recommendation_for_session(
            session_id=pk, user=request.user
        )

        if result is None:
            return Response(
                {"finished": True, "candidate_id": None, "movie": None}
            )

        candidate, recommendation = result
        movie_metadata = fetch_live_display_metadata(
            client=TMDbClient(),
            tmdb_id=recommendation.movie.tmdb_id,
        )
        return Response(
            {
                "finished": False,
                "candidate_id": candidate.id,
                "movie": movie_metadata,
            }
        )


class SwipeSessionCandidateJustificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, candidate_id):
        try:
            _, justification = get_candidate_justification(
                user=request.user, session_id=pk, candidate_id=candidate_id
            )
        except JustificationUnavailableError:
            return Response({"justification": None, "available": False})

        return Response({"justification": justification.text, "available": True})


class SwipeSessionSwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = SwipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = get_user_swipe_session(session_id=pk, user=request.user)
        ensure_session_active(session)

        candidate = get_session_candidate(
            candidate_id=serializer.validated_data["candidate_id"],
            session=session,
        )
        outcome = record_swipe(
            user=request.user,
            candidate=candidate,
            action=serializer.validated_data["action"],
        )
        return Response(
            {"matched": outcome.match is not None, "match": outcome.match},
            status=status.HTTP_201_CREATED,
        )


class SwipeSessionEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_user_swipe_session(session_id=pk, user=request.user)
        summary = end_swipe_session(user=request.user, session=session)

        response = HttpResponse(summary.csv_content, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="ukinory_watchlist.csv"'
        )
        response["X-Swipe-Session-Ended"] = "true"
        return response


class SwipeSessionLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        session = get_user_swipe_session(session_id=pk, user=request.user)
        leave_swipe_session(user=request.user, session=session)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SwipeSessionHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = get_user_swipe_session(session_id=pk, user=request.user)
        ensure_session_active(session)
        touch_session(session.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PairedSwipeSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session, invite = create_paired_session(request.user)
        return Response(
            {
                "session": build_paired_state(session, request.user),
                "invite": InviteSerializer(invite).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PairedSwipeSessionStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = _get_paired_session(request, pk)
        return Response(build_paired_state(session, request.user))


class PairedSwipeSessionInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = _get_paired_session(request, pk)
        invite = regenerate_paired_invite(user=request.user, session=session)
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class SwipeSessionMatchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = _get_paired_session(request, pk)

        candidates = list(matched_candidates(session))
        metadata = (
            fetch_card_metadata_bulk({c.movie.tmdb_id for c in candidates})
            if candidates
            else {}
        )

        payload = []
        for candidate in candidates:
            movie = candidate.movie
            meta = metadata.get(movie.tmdb_id) or {}
            payload.append(
                {
                    "candidate_id": str(candidate.pk),
                    "matched_at": candidate.matched_at,
                    "movie": {
                        "tmdb_id": movie.tmdb_id,
                        "title": meta.get("title") or movie.title,
                        "release_year": meta.get("release_year") or movie.release_year,
                        "poster_url": meta.get("poster_url") or "",
                    },
                }
            )
        return Response(payload)
