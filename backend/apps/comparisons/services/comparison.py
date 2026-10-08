from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.comparisons.dtos.comparison_result import ComparisonResult
from apps.comparisons.exceptions import (
    ComparisonNotFoundError,
    InsufficientDataError,
    NotComparisonMemberError,
)
from apps.comparisons.models import Comparison, ComparisonNarrative
from apps.comparisons.services.metrics import METRICS_VERSION, compute_metrics
from apps.comparisons.services.narrative import ComparisonNarrativeClient
from apps.comparisons.services.snapshot import compute_inputs_hash, load_library
from apps.movies.models import Movie  # adjust the import if Movie lives elsewhere
from apps.movies.services.tmdb_metadata import fetch_card_metadata_bulk
from apps.recommendations.services.joint_profile import (
    DEFAULT_POOL_SIZE,
    JointCandidate,
    calibrate_fits,
    find_joint_candidates,
    user_taste_profiles,
)

RECOMMENDATION_LIMIT = 10
FIT_VERSION = 2


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def list_comparisons(user):
    return Comparison.objects.filter(
        session__users=user
    ).prefetch_related("session__users")


def _get_comparison(user, comparison_id) -> tuple[Comparison, list]:
    try:
        comparison = Comparison.objects.prefetch_related("session__users").get(
            pk=comparison_id
        )
    except (Comparison.DoesNotExist, ValueError, ValidationError) as exc:
        raise ComparisonNotFoundError from exc

    users = sorted(comparison.session.users.all(), key=lambda u: str(u.pk))
    if user.pk not in {u.pk for u in users}:
        raise NotComparisonMemberError
    return comparison, users


def _serialize_candidates(
    candidates: list[JointCandidate],
    reasons: dict[int, str],
    user_ids: list[str],
) -> list[dict]:
    return _json_safe([
        {
            "movie_id": c.movie.pk,
            "title": c.movie.title,
            "release_year": c.movie.release_year,
            "genres": [g.name for g in c.movie.genres.all()],
            "score": round(c.score, 3),
            "fit_version": FIT_VERSION,
            "per_user": {
                uid: round(s, 3) for uid, s in zip(user_ids, c.per_user)
            },
            "justification": reasons.get(i, ""),
        }
        for i, c in enumerate(candidates, 1)
    ])


def attach_tmdb_metadata(payload: dict) -> dict:
    metrics = payload["metrics"]
    agreements = metrics.get("agreements", [])
    divergences = metrics.get("divergences", [])
    recommendations = payload.get("recommendations", [])

    movie_ids = {
        e["movie_id"]
        for items in (agreements, divergences, recommendations)
        for e in items
        if e.get("movie_id") is not None
    }
    if not movie_ids:
        return payload

    tmdb_by_movie = {
        str(pk): tmdb_id
        for pk, tmdb_id in Movie.objects.filter(pk__in=movie_ids).values_list(
            "pk", "tmdb_id"
        )
    }
    metadata = fetch_card_metadata_bulk(set(tmdb_by_movie.values()))

    def enrich(items: list[dict]) -> list[dict]:
        out = []
        for e in items:
            tmdb_id = tmdb_by_movie.get(str(e.get("movie_id")))
            meta = metadata.get(tmdb_id)
            base = {**e, "tmdb_id": tmdb_id}
            if meta is None:
                out.append({**base, "poster_url": ""})
                continue
            enriched = {
                **base,
                "title": meta["title"] or e["title"],
                "release_year": meta["release_year"] or e["release_year"],
                "poster_url": meta["poster_url"],
            }
            if "genres" in e:
                enriched["genres"] = meta["genres"] or e["genres"]
            out.append(enriched)
        return out

    return {
        **payload,
        "metrics": {
            **metrics,
            "agreements": enrich(agreements),
            "divergences": enrich(divergences),
        },
        "recommendations": enrich(recommendations),
    }


def attach_participants(payload: dict, comparison: Comparison, user) -> dict:
    return {
        **payload,
        "participants": {
            str(u.pk): u.username for u in comparison.session.users.all()
        },
        "current_user_id": str(user.pk),
    }


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

    if (
        comparison.inputs_hash != inputs_hash
        or not comparison.metrics_json
        or comparison.metrics_json.get("version") != METRICS_VERSION
    ):
        profiles = user_taste_profiles(users)
        computed = compute_metrics(libs[0], libs[1], profiles[0], profiles[1])
        comparison.metrics_json = _json_safe(
            {
                "version": METRICS_VERSION,
                "public": computed.public,
                "internal": computed.internal,
            }
        )
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
    if (
        cached is not None
        and cached.individual_summaries
        and all(
            r.get("fit_version") == FIT_VERSION for r in cached.recommendations
        )
    ):
        return ComparisonResult(
            comparison, public, cached.narrative_summary,
            cached.recommendations, True,
            individual=cached.individual_summaries,
        )

    profiles = profiles or user_taste_profiles(users)
    pool = find_joint_candidates(
        users=users, profiles=profiles, limit=DEFAULT_POOL_SIZE
    )
    candidates = calibrate_fits(pool, profiles)[:RECOMMENDATION_LIMIT]

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
            "individual_summaries": _json_safe(result.individual),
            "recommendations": recommendations,
            "model_version": client.model,
        },
    )
    comparison.narratives.exclude(inputs_hash=inputs_hash).delete()

    return ComparisonResult(
        comparison, public, result.summary, recommendations, True,
        individual=result.individual,
    )
