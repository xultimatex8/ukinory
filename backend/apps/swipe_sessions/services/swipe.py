from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.enums import SwipeAction
from apps.library.models import WatchlistEntry, WatchlistSource
from apps.swipe_sessions.models import Swipe, SwipeSessionCandidate, SwipeSession
from apps.swipe_sessions.services.session import touch_session
from apps.swipe_sessions.exceptions import CandidateNotFoundError


def get_session_candidate(candidate_id, session) -> SwipeSessionCandidate:
    try:
        return SwipeSessionCandidate.objects.get(
            pk=candidate_id,
            session=session,
        )
    except SwipeSessionCandidate.DoesNotExist as exc:
        raise CandidateNotFoundError from exc


@transaction.atomic
def record_swipe(user, candidate: SwipeSessionCandidate, action: str) -> Swipe:
    swipe = Swipe.objects.create(
        user=user,
        candidate=candidate,
        action=action,
    )

    touch_session(candidate.session_id)

    if action == SwipeAction.WATCHLIST:
        WatchlistEntry.objects.update_or_create(
            user=user,
            title=candidate.movie.title,
            release_year=candidate.movie.release_year,
            defaults={
                "movie": candidate.movie,
                "source": WatchlistSource.SWIPE_ADDED,
                "added_date": timezone.now(),
            },
        )

    return swipe