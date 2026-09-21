from __future__ import annotations

from django.db import models
from pgvector.django import VectorField, HnswIndex

from apps.common.models import BaseModel

EMBEDDING_DIMENSIONS = 768


class Genre(BaseModel):
    wikidata_id = models.CharField(
        max_length=32, unique=True, null=True, blank=True, db_index=True
    )
    name = models.CharField(max_length=100)


class EmbeddingBatchJob(BaseModel):
    class State(models.TextChoices):
        SUBMITTED = "submitted"
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    job_name = models.CharField(max_length=255, unique=True)
    state = models.CharField(
        max_length=16, choices=State.choices, default=State.SUBMITTED, db_index=True
    )
    items = models.JSONField()
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")


class Movie(BaseModel):
    tmdb_id = models.PositiveIntegerField(unique=True, db_index=True)
    wikidata_id = models.CharField(
        max_length=32, unique=True, null=True, blank=True, db_index=True
    )

    title = models.CharField(max_length=255)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    wikidata_description = models.TextField(blank=True, default="")
    runtime = models.PositiveIntegerField(null=True, blank=True)
    original_language = models.CharField(max_length=100, blank=True, default="")
    directors = models.JSONField(null=True, blank=True)

    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    embedding_source_hash = models.CharField(max_length=64, blank=True, default="")
    embedding_target_hash = models.CharField(max_length=64, blank=True, default="")
    embedding_batch = models.ForeignKey(
        EmbeddingBatchJob,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movies",
    )

    genres = models.ManyToManyField(Genre, related_name="movies", blank=True)

    metadata_fetched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When Wikidata metadata was last (re)fetched for this row.",
    )

    class Meta:
        indexes = [
            HnswIndex(
                name="movie_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]