from __future__ import annotations

from django.db import transaction

from apps.recommendations.services.hybrid_pool import build_hybrid_pool
from apps.swipe_sessions.models import SwipeSessionCandidate


@transaction.atomic
def fill_candidate_pool(
    session,
    user,
) -> list[SwipeSessionCandidate]:
    existing_movie_ids = set(session.candidates.values_list("movie_id", flat=True))

    candidates = build_hybrid_pool(user)

    candidates = [candidate for candidate in candidates if candidate.movie.id not in existing_movie_ids]

    last_position = (
        session.candidates
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
        or 0
    )

    session_candidates = [
        SwipeSessionCandidate(
            session=session,
            movie=candidate.movie,
            score=candidate.final_score,
            position=last_position + index,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]

    return SwipeSessionCandidate.objects.bulk_create(session_candidates)
