from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Max, Q

from apps.common.enums import InviteType, SwipeAction, SwipeSessionType
from apps.common.services.session_state import build_participant_state
from apps.common.services.sessions import touch_session
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite
from apps.invites.services.session_invites import regenerate_session_invite
from apps.swipe_sessions.constants import PAIRED_MAX_PARTICIPANTS
from apps.swipe_sessions.exceptions import PairedSessionRequiredError
from apps.swipe_sessions.models import SwipeSession, SwipeSessionCandidate
from apps.swipe_sessions.services.session import create_swipe_session


def require_paired(session: SwipeSession) -> None:
    if session.type != SwipeSessionType.PAIRED:
        raise PairedSessionRequiredError


@transaction.atomic
def create_paired_session(user) -> tuple[SwipeSession, Invite]:
    session = create_swipe_session(user, SwipeSessionType.PAIRED)
    touch_session(session.pk)
    invite = create_invite(
        user=user,
        invite_type=InviteType.PAIRED_SWIPE,
        session=session,
    )
    return session, invite


def regenerate_paired_invite(*, user, session: SwipeSession) -> Invite:
    require_paired(session)
    return regenerate_session_invite(
        user=user, session=session, invite_type=InviteType.PAIRED_SWIPE
    )


def matched_candidates(session: SwipeSession):
    on_watchlist = Q(swipes__action=SwipeAction.WATCHLIST)
    return (
        SwipeSessionCandidate.objects.filter(session=session)
        .annotate(
            watchlist_count=Count("swipes", filter=on_watchlist),
            matched_at=Max("swipes__created_at", filter=on_watchlist),
        )
        .filter(watchlist_count__gte=PAIRED_MAX_PARTICIPANTS)
        .select_related("movie")
        .order_by("-matched_at")
    )


def match_payload(candidate: SwipeSessionCandidate) -> dict:
    movie = candidate.movie
    return {
        "candidate_id": str(candidate.pk),
        "movie_id": str(movie.pk),
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "release_year": movie.release_year,
    }


def build_paired_state(session: SwipeSession, user) -> dict:
    return {
        **build_participant_state(session, user),
        "type": session.type,
        "current_user_id": str(user.pk),
        "matches_count": matched_candidates(session).count(),
    }
