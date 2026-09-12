from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Genre(BaseModel):
    wikidata_id = models.CharField(
        max_length=32, unique=True, null=True, blank=True, db_index=True
    )
    name = models.CharField(max_length=100)


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

    embedding = models.JSONField(null=True, blank=True)
    genres = models.ManyToManyField(Genre, related_name="movies", blank=True)

    metadata_fetched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When Wikidata metadata was last (re)fetched for this row.",
    )
