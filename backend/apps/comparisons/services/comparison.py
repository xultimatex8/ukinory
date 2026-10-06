from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.comparisons.dtos.comparison_result import ComparisonResult
from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)
from apps.comparisons.models import Comparison, ComparisonNarrative
from apps.comparisons.services.metrics import compute_metrics
from apps.comparisons.services.narrative import ComparisonNarrativeClient
from apps.comparisons.services.snapshot import compute_inputs_hash, load_library
from apps.recommendations.services.joint_profile import (
    JointCandidate,
    find_joint_candidates,
    user_taste_profiles,
)

RECOMMENDATION_LIMIT = 10


def list_comparisons(user):
    return Comparison.objects.filter(users=user).prefetch_related("users")


def _get_comparison(user, comparison_id) -> tuple[Comparison, list]:
    try:
        comparison = Comparison.objects.prefetch_related("users").get(
            pk=comparison_id
        )
    except (Comparison.DoesNotExist, ValueError, ValidationError) as exc:
        raise ComparisonNotFoundError from exc

    users = sorted(comparison.users.all(), key=lambda u: str(u.pk))
    if user.pk not in {u.pk for u in users}:
        raise NotComparisonMemberError
    return comparison, users


def _serialize_candidates(
    candidates: list[JointCandidate],
    reasons: dict[int, str],
    user_ids: list[str],
) -> list[dict]:
    return [
        {
            "movie_id": c.movie.pk,
            "title": c.movie.title,
            "release_year": c.movie.release_year,
            "genres": [g.name for g in c.movie.genres.all()],
            "score": round(c.score, 3),
            "per_user": {
                uid: round(s, 3) for uid, s in zip(user_ids, c.per_user)
            },
            "justification": reasons.get(i, ""),
        }
        for i, c in enumerate(candidates, 1)
    ]


def get_comparison_result(*, user, comparison_id) -> ComparisonResult:
    comparison, users = _get_comparison(user, comparison_id)

    if len(users) != 2:
        raise InsufficientDataError("A comparison needs exactly two participants.")

    libs = [load_library(u) for u in users]
    if any(not lib.films for lib in libs):
        raise InsufficientDataError("Both participants need imported ratings.")

    user_ids = [str(u.pk) for u in users]
    inputs_hash = compute_inputs_hash(libs)
    profiles = None

    if comparison.inputs_hash != inputs_hash or not comparison.metrics_json:
        profiles = user_taste_profiles(users)
        computed = compute_metrics(libs[0], libs[1], profiles[0], profiles[1])
        comparison.metrics_json = {
            "public": computed.public,
            "internal": computed.internal,
        }
        comparison.inputs_hash = inputs_hash
        comparison.generated_at = timezone.now()
        comparison.save(
            update_fields=["metrics_json", "inputs_hash", "generated_at"]
        )

    public = comparison.metrics_json["public"]
    internal = comparison.metrics_json["internal"]

    cached = ComparisonNarrative.objects.filter(
        comparison=comparison, inputs_hash=inputs_hash
    ).first()
    if cached is not None:
        return ComparisonResult(
            comparison, public, cached.narrative_summary,
            cached.recommendations, True,
        )

    profiles = profiles or user_taste_profiles(users)
    candidates = find_joint_candidates(
        users=users, profiles=profiles, limit=RECOMMENDATION_LIMIT
    )

    client = ComparisonNarrativeClient()
    result = client.generate(
        public=public, internal=internal, candidates=candidates,
        user_ids=user_ids,
    )

    if result is None:
        return ComparisonResult(
            comparison, public, "",
            _serialize_candidates(candidates, {}, user_ids), False,
        )

    recommendations = _serialize_candidates(candidates, result.reasons, user_ids)
    ComparisonNarrative.objects.update_or_create(
        comparison=comparison, inputs_hash=inputs_hash,
        defaults={
            "narrative_summary": result.summary,
            "recommendations": recommendations,
            "model_version": client.model,
        },
    )
    comparison.narratives.exclude(inputs_hash=inputs_hash).delete()  # stale

    return ComparisonResult(
        comparison, public, result.summary, recommendations, True
    )
