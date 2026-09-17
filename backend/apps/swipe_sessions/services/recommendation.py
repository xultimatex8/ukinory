from __future__ import annotations

from django.conf import settings

from apps.recommendations.dtos.candidate import RecommendationCandidate
from apps.swipe_sessions.models import Swipe, SwipeSession, SwipeSessionCandidate
from apps.swipe_sessions.services.candidate_pool import fill_candidate_pool
from apps.swipe_sessions.exceptions import NotSessionMemberError, SwipeSessionNotFoundError
from apps.swipe_sessions.services.session import ensure_session_active


DEFAULT_POOL_REFILL_THRESHOLD = 5


def get_next_recommendation(
    session,
    user,
) -> tuple[SwipeSessionCandidate, RecommendationCandidate] | None:
    pool_refill_threshhold = getattr(
        settings,
        "POOL_REFILL_THRESHOLD",
        DEFAULT_POOL_REFILL_THRESHOLD,
    )

    candidate = _get_next_candidate(session, user)

    if candidate is None:
        fill_candidate_pool(session=session, user=user)
        candidate = _get_next_candidate(session, user)

    elif _get_remaining_candidates(session, user) <= pool_refill_threshhold:
        fill_candidate_pool(session=session, user=user)

    if candidate is None:
        return None

    justification = getattr(candidate, "justification", None)
    justification_text = justification.text if justification is not None else ""

    recommendation = RecommendationCandidate(
        movie=candidate.movie,
        similarity=candidate.score,
        justification=justification_text,
    )

    return candidate, recommendation


def get_next_recommendation_for_session(
    session_id,
    user,
) -> tuple[SwipeSessionCandidate, RecommendationCandidate] | None:
    try:
        session = SwipeSession.objects.get(pk=session_id)
    except SwipeSession.DoesNotExist as exc:
        raise SwipeSessionNotFoundError from exc

    if not session.users.filter(pk=user.pk).exists():
        raise NotSessionMemberError

    ensure_session_active(session)

    return get_next_recommendation(
        session=session,
        user=user,
    )


def _get_next_candidate(session, user) -> SwipeSessionCandidate | None:
    swiped_candidate_ids = Swipe.objects.filter(
        user=user,
        candidate__session=session,
    ).values("candidate_id")

    return (
        session.candidates
        .exclude(id__in=swiped_candidate_ids)
        .order_by("position")
        .first()
    )


def _get_remaining_candidates(session, user) -> int:
    swiped_candidate_ids = Swipe.objects.filter(
        user=user,
        candidate__session=session,
    ).values("candidate_id")

    return (
        session.candidates
        .exclude(id__in=swiped_candidate_ids)
        .count()
    )
