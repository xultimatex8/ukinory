from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.session import create_swipe_session, end_swipe_session, ensure_session_active, get_user_swipe_session, start_swipe_session, touch_session
from apps.swipe_sessions.serializers import CreateSwipeSessionSerializer, SwipeSerializer, SwipeSessionSerializer
from apps.swipe_sessions.services.recommendation import get_next_recommendation_for_session
from apps.swipe_sessions.services.justification import get_candidate_justification
from apps.swipe_sessions.services.swipe import get_session_candidate, record_swipe
from apps.movies.services.tmdb_client import TMDbClient
from apps.movies.services.tmdb_metadata import fetch_live_display_metadata
from apps.swipe_sessions.exceptions import CandidateNotFoundError, JustificationUnavailableError, NotSessionMemberError, SwipeSessionFinishedError, SwipeSessionNotFoundError
from apps.invites.exceptions import TooManyPendingInvitesError
from apps.invites.serializers import InviteSerializer
from apps.movies.services.tmdb_metadata import fetch_card_metadata_bulk
from apps.swipe_sessions.services.paired import (
    build_paired_state,
    create_paired_session,
    matched_candidates,
    regenerate_paired_invite,
    require_paired,
)


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
        try:
            session = SwipeSession.objects.get(pk=pk)
        except SwipeSession.DoesNotExist:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not session.users.filter(pk=request.user.pk).exists():
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            ensure_session_active(session)
        except SwipeSessionFinishedError:
            return Response({"detail": "This swipe session has already finished."}, status=status.HTTP_409_CONFLICT)

        return Response(SwipeSessionSerializer(session).data)


class SwipeSessionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            session = get_user_swipe_session(
                session_id=pk,
                user=request.user,
            )
        except SwipeSessionNotFoundError:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotSessionMemberError:
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            session = start_swipe_session(request.user, session)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(SwipeSessionSerializer(session).data)


class SwipeSessionRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            result = get_next_recommendation_for_session(
                session_id=pk,
                user=request.user,
            )
        except SwipeSessionNotFoundError:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotSessionMemberError:
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except SwipeSessionFinishedError:
            return Response(
                {"detail": "This swipe session has already finished."},
                status=status.HTTP_409_CONFLICT,
            )

        if result is None:
            return Response(
                {
                    "finished": True,
                    "candidate_id": None,
                    "movie": None,
                },
                status=status.HTTP_200_OK,
            )

        candidate, recommendation = result

        client = TMDbClient()

        movie_metadata = fetch_live_display_metadata(
            client=client,
            tmdb_id=recommendation.movie.tmdb_id,
        )

        return Response(
            {
                "finished": False,
                "candidate_id": candidate.id,
                "movie": movie_metadata,
            },
            status=status.HTTP_200_OK,
        )


class SwipeSessionCandidateJustificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, candidate_id):
        try:
            candidate, justification = get_candidate_justification(
                user=request.user,
                session_id=pk,
                candidate_id=candidate_id,
            )
        except SwipeSessionNotFoundError:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotSessionMemberError:
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except CandidateNotFoundError:
            return Response(
                {"detail": "Candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except SwipeSessionFinishedError:
            return Response(
                {"detail": "This swipe session has already finished."},
                status=status.HTTP_409_CONFLICT,
            )
        except JustificationUnavailableError:
            return Response(
                {
                    "justification": None,
                    "available": False,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "justification": justification.text,
                "available": True,
            }
        )


class SwipeSessionSwipeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = SwipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = get_user_swipe_session(
                session_id=pk,
                user=request.user,
            )
        except SwipeSessionNotFoundError:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotSessionMemberError:
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            ensure_session_active(session)
        except SwipeSessionFinishedError:
            return Response({"detail": "This swipe session has already finished."}, status=status.HTTP_409_CONFLICT)

        try:
            candidate = get_session_candidate(
                candidate_id=serializer.validated_data["candidate_id"],
                session=session,
            )
        except CandidateNotFoundError:
            return Response(
                {"detail": "Candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
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
        try:
            session = get_user_swipe_session(
                session_id=pk,
                user=request.user,
            )
        except SwipeSessionNotFoundError:
            return Response(
                {"detail": "Swipe session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotSessionMemberError:
            return Response(
                {"detail": "You are not a member of this session."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            summary = end_swipe_session(user=request.user, session=session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = HttpResponse(
            summary.csv_content,
            content_type="text/csv",
        )
        response["Content-Disposition"] = (
            'attachment; filename="ukinory_watchlist.csv"'
        )
        response["X-Swipe-Session-Ended"] = "true"

        return response


class SwipeSessionHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            session = get_user_swipe_session(session_id=pk, user=request.user)
        except SwipeSessionNotFoundError:
            return Response({"detail": "Swipe session not found."}, status=status.HTTP_404_NOT_FOUND)
        except NotSessionMemberError:
            return Response({"detail": "You are not a member of this session."}, status=status.HTTP_403_FORBIDDEN)

        try:
            ensure_session_active(session)
        except SwipeSessionFinishedError:
            return Response(
                {"detail": "This swipe session has already finished."},
                status=status.HTTP_409_CONFLICT,
            )

        touch_session(session.pk)

        return Response(status=status.HTTP_204_NO_CONTENT)


def _resolve(request, pk):
    try:
        session = get_user_swipe_session(session_id=pk, user=request.user)
    except SwipeSessionNotFoundError:
        return None, Response(
            {"detail": "Swipe session not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except NotSessionMemberError:
        return None, Response(
            {"detail": "You are not a member of this session."},
            status=status.HTTP_403_FORBIDDEN,
        )
 
    require_paired(session)
    return session, None
 
 
def _too_many_invites() -> Response:
    return Response(
        {"detail": "You have too many pending invites."},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
 
 
class PairedSwipeSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        try:
            session, invite = create_paired_session(request.user)
        except TooManyPendingInvitesError:
            return _too_many_invites()
 
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
        session, error = _resolve(request, pk)
        if error is not None:
            return error
 
        return Response(build_paired_state(session, request.user))
 
 
class PairedSwipeSessionInviteView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request, pk):
        session, error = _resolve(request, pk)
        if error is not None:
            return error
 
        try:
            invite = regenerate_paired_invite(user=request.user, session=session)
        except TooManyPendingInvitesError:
            return _too_many_invites()
 
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)
 
 
class SwipeSessionMatchesView(APIView):
    permission_classes = [IsAuthenticated]
 
    def get(self, request, pk):
        session, error = _resolve(request, pk)
        if error is not None:
            return error
 
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
