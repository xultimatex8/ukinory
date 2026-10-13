from __future__ import annotations

from django.db import transaction

from apps.common.enums import SwipeAction, SwipeSessionType, WatchlistSource
from apps.common.services.sessions import touch_session
from apps.library.services.watchlist import add_movie
from apps.swipe_sessions.dtos.swipe_outcome import SwipeOutcome
from apps.swipe_sessions.exceptions import CandidateNotFoundError
from apps.swipe_sessions.models import Swipe, SwipeSessionCandidate
from apps.swipe_sessions.realtime import notify_session
from apps.swipe_sessions.services.paired import match_payload


def get_session_candidate(candidate_id, session) -> SwipeSessionCandidate:
    try:
        return SwipeSessionCandidate.objects.get(
            pk=candidate_id,
            session=session,
        )
    except SwipeSessionCandidate.DoesNotExist as exc:
        raise CandidateNotFoundError from exc


def _detect_match(user, candidate: SwipeSessionCandidate, action: str) -> dict | None:
    if action != SwipeAction.WATCHLIST:
        return None

    partner_swipes = list(
        Swipe.objects.filter(candidate=candidate, action=SwipeAction.WATCHLIST)
        .exclude(user=user)
        .select_related("user")
    )
    if not partner_swipes:
        return None

    add_movie(user, candidate.movie, WatchlistSource.SWIPE_MATCH, True)
    for partner_swipe in partner_swipes:
        add_movie(partner_swipe.user, candidate.movie, WatchlistSource.SWIPE_MATCH, True)

    return match_payload(candidate)


def _broadcast(user, candidate: SwipeSessionCandidate, action: str, match: dict | None) -> None:
    session_id = candidate.session_id
    swipe_event = {
        "event": "swipe.recorded",
        "user_id": str(user.pk),
        "candidate_id": str(candidate.pk),
        "action": action,
        "title": candidate.movie.title,
        "release_year": candidate.movie.release_year,
    }

    def send() -> None:
        notify_session(session_id, **swipe_event)
        if match is not None:
            notify_session(session_id, event="match", **match)

    transaction.on_commit(send)


@transaction.atomic
def record_swipe(user, candidate: SwipeSessionCandidate, action: str) -> SwipeOutcome:
    paired = candidate.session.type == SwipeSessionType.PAIRED

    if paired:
        candidate = (
            SwipeSessionCandidate.objects.select_for_update(of=("self",))
            .select_related("movie", "session")
            .get(pk=candidate.pk)
        )

    swipe, created = Swipe.objects.get_or_create(
        user=user,
        candidate=candidate,
        defaults={"action": action},
    )
    if not created:
        return SwipeOutcome(swipe=swipe, created=False)

    touch_session(candidate.session_id)

    if action == SwipeAction.WATCHLIST:
        add_movie(user, candidate.movie, WatchlistSource.SWIPE_ADDED)

    if not paired:
        return SwipeOutcome(swipe=swipe)

    match = _detect_match(user, candidate, action)
    _broadcast(user, candidate, action, match)

    return SwipeOutcome(swipe=swipe, match=match)