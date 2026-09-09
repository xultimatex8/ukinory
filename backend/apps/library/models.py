from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.common.enums import WatchlistSource


# Provisional until the creation of movie entity
class ImportedFilmRecordMixin(models.Model):
    title = models.CharField(max_length=255)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class Rating(BaseModel, ImportedFilmRecordMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rating = models.FloatField(null=True, blank=True)
    liked = models.BooleanField(default=False)
    watched_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "title", "release_year"],
                name="unique_rating_per_user_and_film",
            )
        ]


class WatchlistEntry(BaseModel, ImportedFilmRecordMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_entries",
    )
    added_date = models.DateField(null=True, blank=True)
    source = models.CharField(
        choices=WatchlistSource.choices,
        default=WatchlistSource.IMPORTED,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "title", "release_year"],
                name="unique_watchlist_entry_per_user_and_film",
            )
        ]
