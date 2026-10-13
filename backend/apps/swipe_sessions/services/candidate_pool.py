from __future__ import annotations

from django.db import transaction
from django.db.models import Count

from apps.common.enums import SwipeAction
from apps.common.models import Session
from apps.library.models import WatchlistEntry
from apps.movies.models import Movie
from apps.recommendations.services.hybrid_pool import build_hybrid_pool
from apps.recommendations.services.joint_profile import (
    find_joint_candidates,
    user_taste_profiles,
)
from apps.swipe_sessions.constants import PAIRED_MAX_PARTICIPANTS, PAIRED_POOL_SIZE
from apps.swipe_sessions.exceptions import PairedDataMissingError
from apps.swipe_sessions.models import Swipe, SwipeSessionCandidate
from apps.common.exceptions import PartnerNotJoinedError


def _store_candidates(
    session, ranked: list[tuple[Movie, float]]
) -> list[SwipeSessionCandidate]:
    last_position = (
        session.candidates
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
        or 0
    )

    rows = [
        SwipeSessionCandidate(
            session=session,
            movie=movie,
            score=score,
            position=last_position + index,
        )
        for index, (movie, score) in enumerate(ranked, start=1)
    ]

    return SwipeSessionCandidate.objects.bulk_create(rows)


@transaction.atomic
def fill_candidate_pool(
    session,
    user,
) -> list[SwipeSessionCandidate]:
    existing_movie_ids = set(session.candidates.values_list("movie_id", flat=True))

    candidates = build_hybrid_pool(user)

    ranked = [
        (candidate.movie, candidate.final_score)
        for candidate in candidates
        if candidate.movie.id not in existing_movie_ids
    ]

    return _store_candidates(session, ranked)


def _min_remaining(session, users) -> int:
    total = session.candidates.count()
    swiped_by_user = {
        row["user_id"]: row["n"]
        for row in Swipe.objects.filter(candidate__session=session)
        .values("user_id")
        .annotate(n=Count("id"))
    }
    return min(total - swiped_by_user.get(user.pk, 0) for user in users)


def _already_planned_movie_ids(users) -> set:
    planned = set(
        WatchlistEntry.objects.filter(user__in=users, movie__isnull=False)
        .values_list("movie_id", flat=True)
    )
    swiped = set(
        Swipe.objects.filter(user__in=users, action=SwipeAction.WATCHLIST)
        .values_list("candidate__movie_id", flat=True)
    )
    return planned | swiped


@transaction.atomic
def fill_paired_candidate_pool(
    session,
    *,
    refill_threshold: int | None = None,
) -> list[SwipeSessionCandidate]:
    Session.objects.select_for_update().get(pk=session.pk)

    users = list(session.users.all())
    if len(users) < PAIRED_MAX_PARTICIPANTS:
        raise PartnerNotJoinedError

    if refill_threshold is not None and _min_remaining(session, users) > refill_threshold:
        return []

    profiles = user_taste_profiles(users)
    if any(profile is None for profile in profiles):
        raise PairedDataMissingError

    exclude = set(session.candidates.values_list("movie_id", flat=True))
    exclude |= _already_planned_movie_ids(users)

    pool = find_joint_candidates(
        users=users,
        profiles=profiles,
        limit=PAIRED_POOL_SIZE,
        exclude_movie_ids=exclude,
    )

    return _store_candidates(session, [(c.movie, c.score) for c in pool])
