from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class Genre(BaseModel):
    tmdb_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100)


class Movie(BaseModel):
    tmdb_id = models.PositiveIntegerField(unique=True, db_index=True)
    title = models.CharField(max_length=255)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    synopsis = models.TextField(blank=True, default="")
    poster_url = models.URLField(blank=True, default="")
    vote_average = models.FloatField(null=True, blank=True)
    runtime = models.PositiveIntegerField(null=True, blank=True)
    embedding = models.JSONField(null=True, blank=True)
    streaming_providers = models.JSONField(null=True, blank=True)
    genres = models.ManyToManyField(Genre, related_name="movies", blank=True)
    metadata_fetched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When TMDb metadata was last (re)fetched for this row.",
    )
