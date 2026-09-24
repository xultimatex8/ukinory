from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.common import api_quota
from apps.movies.exceptions import EmbeddingUnavailableError
from apps.movies.models import EmbeddingBatchJob, Movie
from apps.movies.services.embedding_client import QUOTA_BATCH, EmbeddingClient
from apps.movies.services.embedding_text import build_embedding_text
from apps.movies.services.movie_cache import embedding_hash

logger = logging.getLogger(__name__)

SUBMIT_LOCK_KEY = "embedding:batch:submit_lock"
SUBMIT_LOCK_TIMEOUT_SECONDS = 600
DEFAULT_MAX_ITEMS = 2000


def pending_movies_queryset():
    return Movie.objects.filter(embedding_batch__isnull=True).filter(
        Q(embedding__isnull=True)
        | (
            ~Q(embedding_target_hash="")
            & ~Q(embedding_source_hash=F("embedding_target_hash"))
        )
    )


def movie_to_metadata(movie: Movie) -> dict:
    return {
        "title": movie.title,
        "release_year": movie.release_year,
        "wikidata_description": movie.wikidata_description or "",
        "genres": [{"name": g.name} for g in movie.genres.all()],
        "directors": movie.directors or [],
        "original_language": movie.original_language,
        "runtime": movie.runtime,
    }


def submit_pending_embeddings_batch(
    client: EmbeddingClient | None = None,
    max_items: int | None = None,
    min_items: int = 1,
) -> EmbeddingBatchJob | None:
    max_items = max_items or DEFAULT_MAX_ITEMS

    budget = api_quota.remaining(QUOTA_BATCH)
    if budget is not None and budget <= 0:
        logger.info("Embedding batch budget exhausted; skipping submission.")
        return None

    if not cache.add(SUBMIT_LOCK_KEY, "1", timeout=SUBMIT_LOCK_TIMEOUT_SECONDS):
        logger.info("Another batch submission is in progress; skipping.")
        return None

    try:
        movies = list(
            pending_movies_queryset()
            .prefetch_related("genres")
            .order_by("pk")[:max_items]
        )
        if len(movies) < min_items:
            logger.info("Only %d pending movie(s); below min_items=%d.", len(movies), min_items)
            return None

        pairs = [(m, build_embedding_text(movie_to_metadata(m))) for m in movies]
        pairs = [(m, t) for m, t in pairs if t.strip()]
        movies = [m for m, _ in pairs]
        texts = [t for _, t in pairs]
        hashes = [embedding_hash(t) for t in texts]
        costs = [api_quota.text_cost(QUOTA_BATCH, t) for t in texts]

        if budget is not None:
            keep, running = 0, 0
            for c in costs:
                if running + c > budget:
                    break
                running += c
                keep += 1
            movies, texts, hashes, costs = (
                movies[:keep], texts[:keep], hashes[:keep], costs[:keep]
            )
        if not movies:
            logger.info("Remaining budget does not fit any pending movie; skipping.")
            return None

        client = client or EmbeddingClient()
        job_name = client.create_batch(
            texts,
            display_name=f"catalog-embeddings-{timezone.now():%Y%m%d%H%M}",
            cost=sum(costs),
        )

        with transaction.atomic():
            job = EmbeddingBatchJob.objects.create(
                job_name=job_name,
                items=[[str(m.pk), h, c] for m, h, c in zip(movies, hashes, costs)],
            )
            Movie.objects.filter(pk__in=[m.pk for m in movies]).update(embedding_batch=job)

        logger.info("Submitted embedding batch %s with %d movie(s).", job_name, len(movies))
        return job
    finally:
        cache.delete(SUBMIT_LOCK_KEY)


def collect_finished_batches(client: EmbeddingClient | None = None) -> dict[str, int]:
    summary = {"succeeded": 0, "failed": 0, "pending": 0, "embedded": 0, "item_errors": 0}

    jobs = list(EmbeddingBatchJob.objects.filter(state=EmbeddingBatchJob.State.SUBMITTED))
    if not jobs:
        return summary

    client = client or EmbeddingClient()

    for job in jobs:
        try:
            result = client.get_batch(job.job_name)
        except EmbeddingUnavailableError as exc:
            logger.warning("Could not poll batch %s: %s", job.job_name, exc)
            summary["pending"] += 1
            continue

        if not result.done:
            summary["pending"] += 1
            continue

        if not result.succeeded:
            _finish_failed(job, f"{result.state}: {result.error or ''}")
            summary["failed"] += 1
            continue

        vectors = result.embeddings or []
        if len(vectors) != len(job.items):
            _finish_failed(
                job,
                f"Result count mismatch: expected {len(job.items)}, got {len(vectors)}.",
            )
            summary["failed"] += 1
            continue

        embedded, errors = _apply_results(job, vectors, result.item_errors or [])
        summary["succeeded"] += 1
        summary["embedded"] += embedded
        summary["item_errors"] += errors

    return summary


def _finish_failed(job: EmbeddingBatchJob, error: str) -> None:
    logger.error("Embedding batch %s failed: %s", job.job_name, error)
    with transaction.atomic():
        Movie.objects.filter(embedding_batch=job).update(embedding_batch=None)
        job.state = EmbeddingBatchJob.State.FAILED
        job.error = error[:2000]
        job.finished_at = timezone.now()
        job.save()

    api_quota.refund(QUOTA_BATCH, sum(item[2] for item in job.items))


def _apply_results(job: EmbeddingBatchJob, vectors: list, item_errors: list[Optional[str]]) -> tuple[int, int]:
    embedded = 0
    errors = 0
    failed_cost = 0

    with transaction.atomic():
        for index, ((movie_id, text_hash, cost), vector) in enumerate(
            zip(job.items, vectors)
        ):
            if vector is None:
                errors += 1
                failed_cost += cost

                error = (
                    item_errors[index]
                    if index < len(item_errors)
                    else "Unknown embedding error."
                )

                logger.error(
                    "Embedding failed for movie %s in batch %s: %s",
                    movie_id,
                    job.job_name,
                    error,
                )
                continue

            updated = (
                Movie.objects.filter(pk=movie_id)
                .filter(
                    Q(embedding_target_hash="")
                    | Q(embedding_target_hash=text_hash)
                )
                .update(
                    embedding=vector,
                    embedding_source_hash=text_hash,
                    embedding_target_hash=text_hash,
                )
            )
            embedded += updated

        Movie.objects.filter(embedding_batch=job).update(embedding_batch=None)
        job.state = EmbeddingBatchJob.State.SUCCEEDED
        job.finished_at = timezone.now()
        job.save()

    if failed_cost:
        api_quota.refund(QUOTA_BATCH, failed_cost)

    logger.info(
        "Embedding batch %s applied: %d embedded, %d item error(s).",
        job.job_name,
        embedded,
        errors,
    )

    return embedded, errors
