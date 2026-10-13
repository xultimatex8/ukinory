from __future__ import annotations

from django.conf import settings

from apps.common.enums import SessionStatus, SwipeSessionType
from apps.recommendations.dtos.candidate import RecommendationCandidate
from apps.swipe_sessions.models import Swipe, SwipeSession, SwipeSessionCandidate
from apps.swipe_sessions.services.candidate_pool import (
    fill_candidate_pool,
    fill_paired_candidate_pool,
)
from apps.swipe_sessions.exceptions import (
    NotSessionMemberError,
    PairedDataMissingError,
    SessionNotStartedError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.services.session import ensure_session_active


DEFAULT_POOL_REFILL_THRESHOLD = 5


def _refill(session, user) -> None:
    if session.type == SwipeSessionType.PAIRED:
        fill_paired_candidate_pool(
            session=session,
            refill_threshold=DEFAULT_POOL_REFILL_THRESHOLD,
        )
    else:
        fill_candidate_pool(session=session, user=user)


def get_next_recommendation(
    session,
    user,
) -> tuple[SwipeSessionCandidate, RecommendationCandidate] | None:
    candidate = _get_next_candidate(session, user)

    try:
        if candidate is None:
            _refill(session, user)
            candidate = _get_next_candidate(session, user)

        elif _get_remaining_candidates(session, user) <= DEFAULT_POOL_REFILL_THRESHOLD:
            _refill(session, user)
    except PairedDataMissingError:
        if candidate is None:
            raise

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

    if session.type == SwipeSessionType.PAIRED and session.status != SessionStatus.ACTIVE:
        raise SessionNotStartedError

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
